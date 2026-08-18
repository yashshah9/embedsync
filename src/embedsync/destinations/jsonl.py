"""JSONL destination — local stand-in until pgvector is wired."""

from __future__ import annotations

import json
from pathlib import Path

from embedsync.destinations.memory import SyncAction


class JsonlDestination:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def apply(self, action: SyncAction, embeddings: list[list[float]], dry_run: bool = False) -> None:
        if dry_run:
            return
        rows = self._load()
        rows = [r for r in rows if r.get("doc_id") != action.doc_id]
        if action.action != "delete":
            for chunk, vector in zip(action.chunks, embeddings, strict=False):
                rows.append(
                    {
                        "chunk_id": chunk.chunk_id,
                        "doc_id": action.doc_id,
                        "content": chunk.content,
                        "embedding": vector,
                    }
                )
        self.path.write_text(
            "\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )

    def _load(self) -> list[dict[object, object]]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        out: list[dict[object, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out
