"""Qdrant destination (optional: pip install 'embedsync[qdrant]')."""

from __future__ import annotations

import os
import uuid
from typing import Any
from urllib.parse import urlparse

from embedsync.destinations.memory import SyncAction

_POINT_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _require_qdrant() -> Any:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise ImportError(
            "qdrant-client is required for the qdrant destination; "
            "install with: pip install 'embedsync[qdrant]'"
        ) from exc
    return QdrantClient


def parse_qdrant_spec(spec: str) -> tuple[str, str]:
    """Parse ``qdrant:URL/collection`` or ``qdrant:URL#collection`` → (url, collection)."""
    raw = spec.split(":", 1)[1] if spec.startswith("qdrant:") else spec
    if "#" in raw:
        url, collection = raw.rsplit("#", 1)
        url, collection = url.rstrip("/"), collection.strip()
        if not url or not collection:
            raise ValueError(f"invalid qdrant destination: {spec!r}")
        return url, collection
    parsed = urlparse(raw)
    path = parsed.path.strip("/")
    if not path or not parsed.netloc:
        raise ValueError(
            f"invalid qdrant destination {spec!r}; use "
            "qdrant:http://host:6333/collection or qdrant:URL#collection"
        )
    parts = path.split("/")
    collection = parts[-1]
    base_path = "/".join(parts[:-1])
    url = f"{parsed.scheme}://{parsed.netloc}"
    if base_path:
        url = f"{url}/{base_path}"
    return url, collection


def _point_id(doc_id: str, chunk_id: str) -> str:
    return str(uuid.uuid5(_POINT_NS, f"{doc_id}:{chunk_id}"))


def _doc_filter(doc_id: str) -> dict[str, Any]:
    return {"must": [{"key": "doc_id", "match": {"value": doc_id}}]}


class QdrantDestination:
    """Upsert/delete points keyed by doc_id + chunk_id."""

    def __init__(
        self,
        url: str,
        collection: str,
        dim: int = 384,
        client: Any | None = None,
        api_key: str | None = None,
    ) -> None:
        self.url = url
        self.collection = collection
        self.dim = dim
        self._ready = False
        if client is not None:
            self._client = client
        else:
            QdrantClient = _require_qdrant()
            key = api_key if api_key is not None else os.environ.get("QDRANT_API_KEY")
            self._client = QdrantClient(url=url, api_key=key or None)

    def _ensure_collection(self, dim: int) -> None:
        if self._ready:
            return
        existing = {c.name for c in self._client.get_collections().collections}
        if self.collection not in existing:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config={"size": int(dim), "distance": "Cosine"},
            )
        self.dim = dim
        self._ready = True

    def apply(self, action: SyncAction, embeddings: list[list[float]], dry_run: bool = False) -> None:
        if dry_run:
            return
        if embeddings:
            self._ensure_collection(len(embeddings[0]))
        else:
            self._ensure_collection(self.dim)

        if action.action == "delete":
            self._client.delete(
                collection_name=self.collection,
                points_selector={"filter": _doc_filter(action.doc_id)},
            )
            return

        if action.action == "add":
            self._client.delete(
                collection_name=self.collection,
                points_selector={"filter": _doc_filter(action.doc_id)},
            )
        else:
            drop_ids = [_point_id(action.doc_id, cid) for cid in action.removed_chunk_ids]
            drop_ids.extend(_point_id(action.doc_id, c.chunk_id) for c in action.chunks)
            if drop_ids:
                self._client.delete(
                    collection_name=self.collection,
                    points_selector={"points": drop_ids},
                )

        points = [
            {
                "id": _point_id(action.doc_id, chunk.chunk_id),
                "vector": vector,
                "payload": {
                    "doc_id": action.doc_id,
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                },
            }
            for chunk, vector in zip(action.chunks, embeddings, strict=False)
        ]
        if points:
            self._client.upsert(collection_name=self.collection, points=points)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
