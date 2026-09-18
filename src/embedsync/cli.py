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
from embedsync.sources.base import Source
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


def _store(state_db: str | None) -> tuple[StateStore, str]:
    settings = Settings()
    path = state_db or settings.state_db
    return StateStore(path), path


def _destination(dest_spec: str) -> MemoryDestination | JsonlDestination:
    if dest_spec == "memory":
        return MemoryDestination()
    if dest_spec.startswith("jsonl:"):
        return JsonlDestination(Path(dest_spec.split(":", 1)[1]))
    if dest_spec.startswith(("pgvector:", "postgresql://", "postgres://")):
        from embedsync.destinations.pgvector import PgVectorDestination

        dsn = dest_spec.split(":", 1)[1] if dest_spec.startswith("pgvector:") else dest_spec
        return PgVectorDestination(dsn)  # type: ignore[return-value]
    if dest_spec.startswith("qdrant:"):
        from embedsync.destinations.qdrant import QdrantDestination, parse_qdrant_spec

        url, collection = parse_qdrant_spec(dest_spec)
        return QdrantDestination(url, collection)  # type: ignore[return-value]
    raise click.UsageError(
        "destination must be 'memory', 'jsonl:/path', 'pgvector:DSN', "
        "postgres(ql)://..., or 'qdrant:URL/collection' / 'qdrant:URL#collection'"
    )


def _source(spec: str, *, max_pages: int) -> Source:
    if spec.startswith("sitemap:"):
        from embedsync.sources.sitemap import SitemapSource, parse_sitemap_spec

        return SitemapSource(parse_sitemap_spec(spec), max_pages=max_pages)
    path = Path(spec)
    if not path.is_dir():
        raise click.UsageError(
            "source must be an existing directory or 'sitemap:https://.../sitemap.xml'"
        )
    return LocalFileSource(path)


@main.command("plan")
@click.argument("source")
@click.option("--state-db", default=None, help="SQLite state database path")
@click.option("--full-reindex", is_flag=True, help="Treat all current docs as updates")
@click.option("--max-pages", default=50, show_default=True, help="Sitemap: max URLs to fetch")
def plan_cmd(source: str, state_db: str | None, full_reindex: bool, max_pages: int) -> None:
    store, path = _store(state_db)
    try:
        sync_plan = plan_sync(_source(source, max_pages=max_pages), store, full_reindex=full_reindex)
    except (ValueError, click.UsageError) as exc:
        store.close()
        if isinstance(exc, click.UsageError):
            raise
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(2) from exc

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
    console.print(f"Total: {sync_plan.total} action(s)  state={path}")
    store.close()


@main.command("run")
@click.argument("source")
@click.option("--dry-run", is_flag=True)
@click.option("--state-db", default=None)
@click.option("--embedder", default="hash")
@click.option(
    "--destination",
    "dest_spec",
    default="memory",
    help="memory | jsonl:/path | pgvector:DSN | postgres(ql)://... | qdrant:URL/collection",
)
@click.option("--full-reindex", is_flag=True, help="Force re-embed all current docs")
@click.option("--max-pages", default=50, show_default=True, help="Sitemap: max URLs to fetch")
def run_cmd(
    source: str,
    dry_run: bool,
    state_db: str | None,
    embedder: str,
    dest_spec: str,
    full_reindex: bool,
    max_pages: int,
) -> None:
    store, path = _store(state_db)
    try:
        dest = _destination(dest_spec)
        report = execute_sync(
            source=_source(source, max_pages=max_pages),
            store=store,
            destination=dest,
            dry_run=dry_run,
            embedder=resolve_embedder(embedder),
            full_reindex=full_reindex,
        )
    except (ValueError, click.UsageError) as exc:
        store.close()
        if isinstance(exc, click.UsageError):
            raise
        console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(2) from exc
    suffix = " (dry-run)" if dry_run else ""
    console.print(
        f"Applied {len(report.actions)} action(s), "
        f"wrote {report.embeddings_written} embedding(s){suffix}  state={path}"
    )
    store.close()


if __name__ == "__main__":
    main()
