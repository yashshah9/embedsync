"""Regression: incomplete Notion/sitemap list must not DELETE existing docs."""

from __future__ import annotations

from pathlib import Path

from embedsync.sources.local import SourceDocument
from embedsync.state.store import StateStore
from embedsync.sync.engine import execute_sync, plan_sync


class _FlipSource:
    """First list returns both docs; second would drop one (old bug path)."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_list_incomplete = False

    def list_documents(self) -> list[SourceDocument]:
        self.calls += 1
        docs = [
            SourceDocument(doc_id="a", content="# A\n\none", metadata={}),
            SourceDocument(doc_id="b", content="# B\n\ntwo", metadata={}),
        ]
        if self.calls > 1:
            # Simulate flaky second fetch dropping b — execute_sync must not re-list.
            return docs[:1]
        return docs


class _IncompleteSource:
    def __init__(self) -> None:
        self.last_list_incomplete = True

    def list_documents(self) -> list[SourceDocument]:
        return [SourceDocument(doc_id="keep", content="# K\n\nx", metadata={})]


def test_execute_sync_lists_documents_once(tmp_path: Path) -> None:
    src = _FlipSource()
    store = StateStore(str(tmp_path / "s.db"))
    report = execute_sync(src, store, dry_run=False)
    assert src.calls == 1
    assert report.embeddings_written >= 2
    store.close()


def test_incomplete_source_skips_deletes(tmp_path: Path) -> None:
    store = StateStore(str(tmp_path / "s.db"))
    # Seed an old doc that is missing from the incomplete list.
    from embedsync.state.store import DocumentState, content_hash

    store.upsert(DocumentState(doc_id="stale", content_hash=content_hash("old"), chunk_count=1))
    src = _IncompleteSource()
    plan = plan_sync(src, store)
    assert plan.deletes == []
    assert any(a.doc_id == "keep" for a in plan.adds)
    store.close()
