"""Stable-ish chunking for documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    content: str
    index: int


def chunk_document(doc_id: str, content: str, size: int = 500) -> list[Chunk]:
    """Split on paragraph boundaries, then pad to size.

    ponytail: hash of (doc_id, index, first 64 chars) — upgrade to simhash merge in M4.
    """
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [content]
    pieces: list[str] = []
    buf = ""
    for para in paragraphs:
        if buf and len(buf) + len(para) > size:
            pieces.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}".strip() if buf else para
    if buf:
        pieces.append(buf)
    chunks: list[Chunk] = []
    for index, text in enumerate(pieces):
        digest = hashlib.sha256(f"{doc_id}:{index}:{text[:64]}".encode()).hexdigest()[:16]
        chunks.append(Chunk(chunk_id=digest, doc_id=doc_id, content=text, index=index))
    return chunks
