"""CLI for embedsync."""

import sys
from pathlib import Path

import click
import structlog
from rich.console import Console
from rich.table import Table

from embedsync import __version__
from embedsync.config import Settings
from embedsync.destinations.memory import MemoryDestination
from embedsync.sources.local import LocalFileSource
from embedsync.state.store import StateStore
from embedsync.sync.engine import execute_sync, plan_sync

console = Console()
log = structlog.get_logger()


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
    for action in sync_plan.adds:
        table.add_row("[green]ADD[/green]", action.doc_id)
    for action in sync_plan.updates:
        table.add_row("[yellow]UPDATE[/yellow]", action.doc_id)
    for action in sync_plan.deletes:
        table.add_row("[red]DELETE[/red]", action.doc_id)
    console.print(table)
    console.print(f"Total: {sync_plan.total} action(s)")
    store.close()


@main.command("run")
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True)
@click.option("--state-db", default=None)
def run_cmd(source_dir: Path, dry_run: bool, state_db: str | None) -> None:
    settings = Settings()
    store = StateStore(state_db or settings.state_db)
    source = LocalFileSource(source_dir)
    dest = MemoryDestination()
    report = execute_sync(source, store, dest, dry_run=dry_run)
    console.print(f"Applied {len(report.actions)} action(s)" + (" (dry-run)" if dry_run else ""))
    store.close()


if __name__ == "__main__":
    main()
