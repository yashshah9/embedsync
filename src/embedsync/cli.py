"""CLI for embedsync."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from embedsync import __version__
from embedsync.config import Settings
from embedsync.destinations.jsonl import JsonlDestination
from embedsync.destinations.memory import MemoryDestination
from embedsync.embedders import resolve_embedder
from embedsync.sources.local import LocalFileSource
from embedsync.state.store import StateStore
from embedsync.sync.engine import execute_sync, plan_sync

console = Console()


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Incremental sync between documents and vector indexes."""


@main.command("health")
def health() -> None:
    console.print(f"[green]embedsync {__version__} OK[/green]")


@main.command("plan")
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--state-db", default=None, help="SQLite state database path")
def plan_cmd(source_dir: Path, state_db: str | None) -> None:
    settings = Settings()
    store = StateStore(state_db or settings.state_db)
    source = LocalFileSource(source_dir)
    sync_plan = plan_sync(source, store)

    table = Table(title="Sync Plan (dry)")
    table.add_column("Action")
    table.add_column("Doc ID")
    table.add_column("Chunks")
    for action in sync_plan.adds:
        table.add_row("[green]ADD[/green]", action.doc_id, str(action.chunk_count))
    for action in sync_plan.updates:
        table.add_row("[yellow]UPDATE[/yellow]", action.doc_id, str(action.chunk_count))
    for action in sync_plan.deletes:
        table.add_row("[red]DELETE[/red]", action.doc_id, "0")
    console.print(table)
    console.print(f"Total: {sync_plan.total} action(s)")
    store.close()


@main.command("run")
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True)
@click.option("--state-db", default=None)
@click.option("--embedder", default="hash")
@click.option("--destination", "dest_spec", default="memory", help="memory | jsonl:/path")
def run_cmd(
    source_dir: Path,
    dry_run: bool,
    state_db: str | None,
    embedder: str,
    dest_spec: str,
) -> None:
    settings = Settings()
    store = StateStore(state_db or settings.state_db)
    source = LocalFileSource(source_dir)
    if dest_spec.startswith("jsonl:"):
        dest = JsonlDestination(Path(dest_spec.split(":", 1)[1]))
    else:
        dest = MemoryDestination()
    report = execute_sync(
        source,
        store,
        destination=dest,
        dry_run=dry_run,
        embedder=resolve_embedder(embedder),
    )
    suffix = " (dry-run)" if dry_run else ""
    console.print(
        f"Applied {len(report.actions)} action(s), "
        f"wrote {report.embeddings_written} embedding(s){suffix}"
    )
    store.close()


if __name__ == "__main__":
    main()
