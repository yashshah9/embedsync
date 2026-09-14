"""Unit tests for PgVectorDestination (mocked connection)."""

from __future__ import annotations

from unittest.mock import MagicMock

from embedsync.chunking import Chunk
from embedsync.destinations.memory import SyncAction
from embedsync.destinations.pgvector import PgVectorDestination


def _mock_conn() -> tuple[MagicMock, MagicMock]:
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    return conn, cur


def test_construct_creates_extension() -> None:
    conn, cur = _mock_conn()
    dest = PgVectorDestination("postgresql://unused", conn=conn)
    assert dest.dim == 384
    cur.execute.assert_called_once()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in cur.execute.call_args[0][0]
    conn.commit.assert_called()


def test_apply_add_upserts_with_expected_sql() -> None:
    conn, cur = _mock_conn()
    dest = PgVectorDestination("postgresql://unused", dim=2, conn=conn)
    cur.reset_mock()
    conn.commit.reset_mock()

    action = SyncAction(
        "add",
        "doc-a",
        chunk_count=1,
        chunks=[Chunk(chunk_id="c1", doc_id="doc-a", content="hello", index=0)],
    )
    dest.apply(action, [[0.1, 0.2]])

    sqls = [c.args[0] for c in cur.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS embedsync_chunks" in s for s in sqls)
    assert any("vector(2)" in s for s in sqls)
    assert any("DELETE FROM embedsync_chunks WHERE doc_id = %s" in s for s in sqls)
    insert = next(c for c in cur.execute.call_args_list if "INSERT INTO embedsync_chunks" in c.args[0])
    assert insert.args[1] == ("doc-a", "c1", "hello", "[0.1,0.2]")
    conn.commit.assert_called()


def test_apply_delete() -> None:
    conn, cur = _mock_conn()
    dest = PgVectorDestination("postgresql://unused", conn=conn)
    cur.reset_mock()

    dest.apply(SyncAction("delete", "doc-a"), [])
    assert any(
        "DELETE FROM embedsync_chunks WHERE doc_id = %s" in c.args[0]
        and c.args[1] == ("doc-a",)
        for c in cur.execute.call_args_list
    )


def test_apply_update_drops_removed_then_upserts() -> None:
    conn, cur = _mock_conn()
    dest = PgVectorDestination("postgresql://unused", dim=2, conn=conn)
    cur.reset_mock()

    action = SyncAction(
        "update",
        "doc-a",
        chunk_count=1,
        chunks=[Chunk(chunk_id="c2", doc_id="doc-a", content="world", index=1)],
        removed_chunk_ids=["c0"],
    )
    dest.apply(action, [[0.3, 0.4]])

    drop_call = next(
        c
        for c in cur.execute.call_args_list
        if "chunk_id = ANY(%s)" in c.args[0]
    )
    assert drop_call.args[1] == ("doc-a", ["c0", "c2"])
