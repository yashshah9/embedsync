"""Pluggable embedding functions."""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.request
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


class OllamaEmbedder:
    """Call a local Ollama /api/embeddings endpoint (stdlib urllib)."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        host: str | None = None,
        dimension: int | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.host = (host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
        self.dimension = dimension or 0
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            payload = json.dumps({"model": self.model, "prompt": text}).encode()
            req = urllib.request.Request(
                f"{self.host}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode())
            except urllib.error.URLError as exc:
                raise RuntimeError(f"Ollama embed failed: {exc}") from exc
            vector = body.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("Ollama response missing embedding vector")
            if self.dimension and len(vector) != self.dimension:
                raise RuntimeError(
                    f"Ollama returned dim {len(vector)}, expected {self.dimension}"
                )
            if not self.dimension:
                self.dimension = len(vector)
            vectors.append([float(x) for x in vector])
        return vectors


def resolve_embedder(name: str) -> Embedder:
    if name in {"hash", "test"}:
        return HashEmbedder()
    if name == "ollama" or name.startswith("ollama:"):
        model = name.split(":", 1)[1] if ":" in name else "nomic-embed-text"
        return OllamaEmbedder(model=model)
    raise ValueError(
        f"Unknown embedder '{name}'. Use hash, ollama, or ollama:<model>."
    )
