"""Unit tests for QdrantDestination (mocked client)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from embedsync.chunking import Chunk
from embedsync.destinations.memory import SyncAction
from embedsync.destinations.qdrant import (
    QdrantDestination,
    _point_id,
    parse_qdrant_spec,
)


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(collections=[])
    return client


def test_parse_path_collection() -> None:
    url, collection = parse_qdrant_spec("qdrant:http://localhost:6333/mycol")
    assert url == "http://localhost:6333"
    assert collection == "mycol"


def test_parse_hash_collection() -> None:
    url, collection = parse_qdrant_spec("qdrant:http://localhost:6333#docs")
    assert url == "http://localhost:6333"
    assert collection == "docs"


def test_apply_add_deletes_then_upserts() -> None:
    client = _mock_client()
    dest = QdrantDestination("http://localhost:6333", "col", dim=2, client=client)
    action = SyncAction(
        "add",
        "doc-a",
        chunk_count=1,
        chunks=[Chunk(chunk_id="c1", doc_id="doc-a", content="hello", index=0)],
    )
    dest.apply(action, [[0.1, 0.2]])

    client.create_collection.assert_called_once()
    delete = client.delete.call_args
    assert delete.kwargs["collection_name"] == "col"
    assert delete.kwargs["points_selector"] == {
        "filter": {"must": [{"key": "doc_id", "match": {"value": "doc-a"}}]}
    }
    upsert = client.upsert.call_args
    assert upsert.kwargs["collection_name"] == "col"
    points = upsert.kwargs["points"]
    assert len(points) == 1
    assert points[0]["id"] == _point_id("doc-a", "c1")
    assert points[0]["vector"] == [0.1, 0.2]
    assert points[0]["payload"]["content"] == "hello"


def test_apply_delete() -> None:
    client = _mock_client()
    dest = QdrantDestination("http://localhost:6333", "col", client=client)
    dest.apply(SyncAction("delete", "doc-a"), [])
    assert client.delete.call_args.kwargs["points_selector"] == {
        "filter": {"must": [{"key": "doc_id", "match": {"value": "doc-a"}}]}
    }
    client.upsert.assert_not_called()


def test_apply_update_drops_removed_then_upserts() -> None:
    client = _mock_client()
    dest = QdrantDestination("http://localhost:6333", "col", dim=2, client=client)
    action = SyncAction(
        "update",
        "doc-a",
        chunk_count=1,
        chunks=[Chunk(chunk_id="c2", doc_id="doc-a", content="world", index=1)],
        removed_chunk_ids=["c0"],
    )
    dest.apply(action, [[0.3, 0.4]])

    drop = client.delete.call_args
    assert drop.kwargs["points_selector"] == {
        "points": [_point_id("doc-a", "c0"), _point_id("doc-a", "c2")]
    }
    points = client.upsert.call_args.kwargs["points"]
    assert points[0]["id"] == _point_id("doc-a", "c2")
