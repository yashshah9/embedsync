"""Scenario tests for embedsync 0.5 behavior."""

from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from embedsync.cli import _destination, main
from embedsync.destinations.jsonl import JsonlDestination
from embedsync.destinations.memory import MemoryDestination
from embedsync.embedders import HashEmbedder, OllamaEmbedder, resolve_embedder
from embedsync.sources.local import LocalFileSource
from embedsync.state.store import StateStore
from embedsync.sync.engine import execute_sync, plan_sync

DOCS = Path(__file__).parent.parent / "examples" / "docs"


def _docs(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_full_reindex_forces_rewrite_when_unchanged(tmp_path: Path) -> None:
    store = StateStore(str(tmp_path / "state.db"))
    source = LocalFileSource(DOCS)
    dest = MemoryDestination()
    first = execute_sync(source, store, dest)
    assert first.embeddings_written > 0
    assert execute_sync(source, store, dest).embeddings_written == 0
    third = execute_sync(source, store, dest, full_reindex=True)
    assert third.embeddings_written == first.embeddings_written
    store.close()


def test_plan_adds_new_documents(tmp_path: Path) -> None:
    docs = _docs(tmp_path, {"a.md": "alpha content here"})
    store = StateStore(str(tmp_path / "state.db"))
    plan = plan_sync(LocalFileSource(docs), store)
    assert len(plan.adds) == 1
    assert plan.adds[0].doc_id == "a.md"
    assert plan.updates == []
    assert plan.deletes == []
    store.close()


def test_plan_updates_changed_documents(tmp_path: Path) -> None:
    docs = _docs(tmp_path, {"a.md": "original text"})
    store = StateStore(str(tmp_path / "state.db"))
    execute_sync(LocalFileSource(docs), store, MemoryDestination())
    (docs / "a.md").write_text("changed text", encoding="utf-8")
    plan = plan_sync(LocalFileSource(docs), store)
    assert plan.adds == []
    assert len(plan.updates) == 1
    assert plan.updates[0].doc_id == "a.md"
    store.close()


def test_plan_deletes_removed_documents(tmp_path: Path) -> None:
    docs = _docs(tmp_path, {"keep.md": "keep", "gone.md": "gone"})
    store = StateStore(str(tmp_path / "state.db"))
    execute_sync(LocalFileSource(docs), store, MemoryDestination())
    (docs / "gone.md").unlink()
    plan = plan_sync(LocalFileSource(docs), store)
    assert len(plan.deletes) == 1
    assert plan.deletes[0].doc_id == "gone.md"
    store.close()


def test_plan_full_reindex_marks_existing_as_updates(tmp_path: Path) -> None:
    docs = _docs(tmp_path, {"a.md": "stable"})
    store = StateStore(str(tmp_path / "state.db"))
    execute_sync(LocalFileSource(docs), store, MemoryDestination())
    plan = plan_sync(LocalFileSource(docs), store, full_reindex=True)
    assert plan.adds == []
    assert len(plan.updates) == 1
    store.close()


def test_idempotent_run_writes_zero_on_second_pass(tmp_path: Path) -> None:
    store = StateStore(str(tmp_path / "state.db"))
    source = LocalFileSource(DOCS)
    dest = MemoryDestination()
    first = execute_sync(source, store, dest)
    second = execute_sync(source, store, dest)
    assert first.embeddings_written > 0
    assert second.embeddings_written == 0
    assert second.actions == []
    store.close()


def test_hash_embedder_dimension() -> None:
    emb = HashEmbedder(dimension=16)
    vectors = emb.embed(["hello", "world"])
    assert emb.dimension == 16
    assert len(vectors) == 2
    assert all(len(v) == 16 for v in vectors)


def test_hash_embedder_stability() -> None:
    emb = HashEmbedder(dimension=8)
    a = emb.embed(["stable text"])[0]
    b = emb.embed(["stable text"])[0]
    c = emb.embed(["different"])[0]
    assert a == b
    assert a != c


def test_resolve_ollama_default_model() -> None:
    emb = resolve_embedder("ollama")
    assert isinstance(emb, OllamaEmbedder)
    assert emb.model == "nomic-embed-text"


def test_resolve_ollama_colon_model() -> None:
    emb = resolve_embedder("ollama:mxbai-embed-large")
    assert isinstance(emb, OllamaEmbedder)
    assert emb.model == "mxbai-embed-large"


def test_bad_destination_raises() -> None:
    with pytest.raises(click.UsageError, match="memory.*jsonl"):
        _destination("pgvector://localhost")


def test_empty_source_dir_cli_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    runner = CliRunner()
    # Empty dir is valid for click Path, but plan reports zero actions (no docs).
    result = runner.invoke(
        main,
        ["plan", str(empty), "--state-db", str(tmp_path / "state.db")],
    )
    assert result.exit_code == 0
    assert "Total: 0 action(s)" in result.output


def test_missing_source_dir_cli_error(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["plan", str(tmp_path / "does-not-exist"), "--state-db", str(tmp_path / "state.db")],
    )
    assert result.exit_code != 0


def test_bad_destination_cli_error(tmp_path: Path) -> None:
    docs = _docs(tmp_path, {"a.md": "hi"})
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run",
            str(docs),
            "--state-db",
            str(tmp_path / "state.db"),
            "--destination",
            "bogus",
        ],
    )
    assert result.exit_code != 0


def test_jsonl_destination_write_roundtrip(tmp_path: Path) -> None:
    docs = _docs(tmp_path, {"note.md": "jsonl roundtrip content"})
    out = tmp_path / "out" / "embeddings.jsonl"
    store = StateStore(str(tmp_path / "state.db"))
    dest = JsonlDestination(out)
    report = execute_sync(LocalFileSource(docs), store, dest)
    assert report.embeddings_written > 0
    assert out.exists()
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == report.embeddings_written
    assert all("embedding" in r and "chunk_id" in r and r["doc_id"] == "note.md" for r in rows)
    store.close()


def test_dry_run_writes_zero_embeddings(tmp_path: Path) -> None:
    store = StateStore(str(tmp_path / "state.db"))
    dest = MemoryDestination()
    report = execute_sync(LocalFileSource(DOCS), store, dest, dry_run=True)
    assert report.embeddings_written == 0
    assert dest.indexed == {}
    assert dest.vectors == {}
    assert store.all_ids() == set()
    store.close()
