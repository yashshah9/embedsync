"""Pluggable embedding functions."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol


class Embedder(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbedder:
    """Deterministic embedding for tests and offline dry-runs (not semantic)."""

    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            raw = [(digest[i % len(digest)] / 255.0) * 2 - 1 for i in range(self.dimension)]
            norm = math.sqrt(sum(x * x for x in raw)) or 1.0
            vectors.append([x / norm for x in raw])
        return vectors


def resolve_embedder(name: str) -> Embedder:
    if name in {"hash", "test"}:
        return HashEmbedder()
    raise ValueError(f"Unknown embedder '{name}'. v0.2 ships hash; openai/nomic come next.")
