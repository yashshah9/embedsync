"""Sync state persistence."""

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentState:
    doc_id: str
    content_hash: str
    chunk_count: int = 0


class StateStore:
    """SQLite-backed document state tracking."""

    def __init__(self, db_path: str) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def get(self, doc_id: str) -> DocumentState | None:
        row = self._conn.execute(
            "SELECT doc_id, content_hash, chunk_count FROM documents WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        if row is None:
            return None
        return DocumentState(doc_id=row[0], content_hash=row[1], chunk_count=row[2])

    def upsert(self, state: DocumentState) -> None:
        self._conn.execute(
            """
            INSERT INTO documents (doc_id, content_hash, chunk_count)
            VALUES (?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET content_hash=excluded.content_hash,
                chunk_count=excluded.chunk_count
            """,
            (state.doc_id, state.content_hash, state.chunk_count),
        )
        self._conn.commit()

    def delete(self, doc_id: str) -> None:
        self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        self._conn.commit()

    def all_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT doc_id FROM documents").fetchall()
        return {r[0] for r in rows}

    def close(self) -> None:
        self._conn.close()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
