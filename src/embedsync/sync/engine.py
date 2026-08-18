"""Core sync engine — diff source against state, plan actions, embed deltas."""

from dataclasses import dataclass, field

import structlog

from embedsync.chunking import chunk_document
from embedsync.destinations.memory import Destination, DestinationReport, MemoryDestination, SyncAction
from embedsync.embedders import Embedder, HashEmbedder
from embedsync.sources.local import LocalFileSource
from embedsync.state.store import DocumentState, StateStore, content_hash

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
    docs = {doc.doc_id: doc for doc in source.list_documents()}

    for doc_id, doc in docs.items():
        current_ids.add(doc_id)
        digest = content_hash(doc.content)
        existing = store.get(doc_id)
        chunks = chunk_document(doc_id, doc.content)
        action = SyncAction(
            "add" if existing is None else "update",
            doc_id,
            chunk_count=len(chunks),
            chunks=chunks,
        )
        if existing is None:
            plan.adds.append(action)
        elif existing.content_hash != digest:
            action.action = "update"
            plan.updates.append(action)

    for stale_id in store.all_ids() - current_ids:
        plan.deletes.append(SyncAction("delete", stale_id))

    log.info("sync_planned", adds=len(plan.adds), updates=len(plan.updates), deletes=len(plan.deletes))
    return plan


def execute_sync(
    source: LocalFileSource,
    store: StateStore,
    destination: Destination | None = None,
    dry_run: bool = False,
    embedder: Embedder | None = None,
) -> DestinationReport:
    dest: Destination = destination or MemoryDestination()
    encoder = embedder or HashEmbedder()
    plan = plan_sync(source, store)
    report = DestinationReport()
    docs = {d.doc_id: d for d in source.list_documents()}

    for action in plan.adds + plan.updates:
        texts = [c.content for c in action.chunks]
        vectors = encoder.embed(texts) if texts else []
        report.actions.append(action)
        report.embeddings_written += 0 if dry_run else len(vectors)
        dest.apply(action, vectors, dry_run=dry_run)
        if not dry_run:
            store.upsert(
                DocumentState(
                    doc_id=action.doc_id,
                    content_hash=content_hash(docs[action.doc_id].content),
                    chunk_count=action.chunk_count,
                )
            )

    for action in plan.deletes:
        report.actions.append(action)
        dest.apply(action, [], dry_run=dry_run)
        if not dry_run:
            store.delete(action.doc_id)

    return report
