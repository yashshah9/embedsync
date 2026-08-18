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


def test_update_reembeds_changed_chunks_only(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    first = ("alpha " * 80).strip()
    second = ("beta " * 80).strip()
    (docs / "note.md").write_text(f"{first}\n\n{second}\n", encoding="utf-8")
    store = StateStore(str(tmp_path / "state.db"))
    source = LocalFileSource(docs)
    dest = MemoryDestination()
    initial = execute_sync(source, store, dest)
    assert initial.embeddings_written >= 2
    (docs / "note.md").write_text(f"{first}\n\n{('gamma ' * 80).strip()}\n", encoding="utf-8")
    source = LocalFileSource(docs)
    again = execute_sync(source, store, dest)
    assert again.embeddings_written == 1
    store.close()
