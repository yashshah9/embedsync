"""Source Protocol shared by local files, sitemaps, etc."""

from __future__ import annotations

from typing import Protocol

from embedsync.sources.local import SourceDocument


class Source(Protocol):
    def list_documents(self) -> list[SourceDocument]:
        ...
