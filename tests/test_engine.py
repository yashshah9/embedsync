"""Tests for embedsync engine."""

from pathlib import Path

from embedsync.destinations.memory import MemoryDestination
from embedsync.sources.local import LocalFileSource
from embedsync.state.store import StateStore
from embedsync.sync.engine import execute_sync, plan_sync

DOCS = Path(__file__).parent.parent / "examples" / "docs"


def test_plan_detects_new_documents(tmp_path: Path) -> None:
    store = StateStore(str(tmp_path / "state.db"))
    source = LocalFileSource(DOCS)
    plan = plan_sync(source, store)
    assert len(plan.adds) == 2
    store.close()


def test_run_indexes_documents(tmp_path: Path) -> None:
    store = StateStore(str(tmp_path / "state.db"))
    source = LocalFileSource(DOCS)
    dest = MemoryDestination()
    first = execute_sync(source, store, dest)
    assert len(dest.indexed) == 2
    assert first.embeddings_written > 0
    second = execute_sync(source, store, dest)
    assert second.embeddings_written == 0
    store.close()
