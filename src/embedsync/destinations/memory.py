"""Vector index destinations (stub for MVP)."""

from dataclasses import dataclass, field


@dataclass
class SyncAction:
    action: str  # add | update | delete
    doc_id: str
    chunk_count: int = 0


@dataclass
class DestinationReport:
    actions: list[SyncAction] = field(default_factory=list)


class MemoryDestination:
    """In-memory destination for dry-run and testing."""

    def __init__(self) -> None:
        self.indexed: dict[str, int] = {}

    def apply(self, action: SyncAction, dry_run: bool = False) -> None:
        if dry_run:
            return
        if action.action == "delete":
            self.indexed.pop(action.doc_id, None)
        else:
            self.indexed[action.doc_id] = action.chunk_count
