"""Destination protocol and in-memory implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from embedsync.chunking import Chunk


@dataclass
class SyncAction:
    action: str  # add | update | delete
    doc_id: str
    chunk_count: int = 0
    chunks: list[Chunk] = field(default_factory=list)
    removed_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class DestinationReport:
    actions: list[SyncAction] = field(default_factory=list)
    embeddings_written: int = 0


class Destination(Protocol):
    def apply(self, action: SyncAction, embeddings: list[list[float]], dry_run: bool = False) -> None:
        ...


class MemoryDestination:
    """In-memory destination for dry-run and testing."""

    def __init__(self) -> None:
        self.indexed: dict[str, int] = {}
        self.vectors: dict[str, dict[str, list[float]]] = {}

    def apply(self, action: SyncAction, embeddings: list[list[float]], dry_run: bool = False) -> None:
        if dry_run:
            return
        if action.action == "delete":
            self.indexed.pop(action.doc_id, None)
            self.vectors.pop(action.doc_id, None)
            return
        bucket = self.vectors.setdefault(action.doc_id, {})
        if action.action == "add":
            bucket.clear()
        for chunk_id in action.removed_chunk_ids:
            bucket.pop(chunk_id, None)
        for chunk, vector in zip(action.chunks, embeddings, strict=False):
            bucket[chunk.chunk_id] = vector
        self.indexed[action.doc_id] = action.chunk_count
