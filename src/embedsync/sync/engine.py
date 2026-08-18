"""Core sync engine — diff source against state, plan actions."""

from dataclasses import dataclass, field

import structlog

from embedsync.destinations.memory import DestinationReport, MemoryDestination, SyncAction
from embedsync.sources.local import LocalFileSource
from embedsync.state.store import StateStore, content_hash

log = structlog.get_logger()


@dataclass
class SyncPlan:
    adds: list[SyncAction] = field(default_factory=list)
    updates: list[SyncAction] = field(default_factory=list)
    deletes: list[SyncAction] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.adds) + len(self.updates) + len(self.deletes)


def plan_sync(source: LocalFileSource, store: StateStore) -> SyncPlan:
    """Compute add/update/delete plan without touching the destination."""
    plan = SyncPlan()
    current_ids: set[str] = set()
    chunk_size = 500  # ponytail: fixed chunk heuristic for MVP

    for doc in source.list_documents():
        current_ids.add(doc.doc_id)
        digest = content_hash(doc.content)
        existing = store.get(doc.doc_id)
        chunks = max(1, len(doc.content) // chunk_size)

        if existing is None:
            plan.adds.append(SyncAction("add", doc.doc_id, chunks))
        elif existing.content_hash != digest:
            plan.updates.append(SyncAction("update", doc.doc_id, chunks))

    for stale_id in store.all_ids() - current_ids:
        plan.deletes.append(SyncAction("delete", stale_id))

    log.info("sync_planned", adds=len(plan.adds), updates=len(plan.updates), deletes=len(plan.deletes))
    return plan


def execute_sync(
    source: LocalFileSource,
    store: StateStore,
    destination: MemoryDestination,
    dry_run: bool = False,
) -> DestinationReport:
    plan = plan_sync(source, store)
    report = DestinationReport()

    for action in plan.adds + plan.updates:
        report.actions.append(action)
        destination.apply(action, dry_run=dry_run)
        if not dry_run:
            doc = next(d for d in source.list_documents() if d.doc_id == action.doc_id)
            from embedsync.state.store import DocumentState

            store.upsert(
                DocumentState(
                    doc_id=action.doc_id,
                    content_hash=content_hash(doc.content),
                    chunk_count=action.chunk_count,
                )
            )

    for action in plan.deletes:
        report.actions.append(action)
        destination.apply(action, dry_run=dry_run)
        if not dry_run:
            store.delete(action.doc_id)

    return report
