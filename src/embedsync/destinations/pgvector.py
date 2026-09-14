"""PostgreSQL + pgvector destination (optional: pip install 'embedsync[pg]')."""

from __future__ import annotations

from typing import Any

from embedsync.destinations.memory import SyncAction


def _require_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as exc:
        raise ImportError(
            "psycopg is required for the pgvector destination; "
            "install with: pip install 'embedsync[pg]'"
        ) from exc
    return psycopg


def _vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vector) + "]"


class PgVectorDestination:
    """Write sync actions into an ``embedsync_chunks`` table."""

    def __init__(self, dsn: str, dim: int = 384, conn: Any | None = None) -> None:
        self.dim = dim
        self._table_ready = False
        if conn is not None:
            self._conn = conn
        else:
            psycopg = _require_psycopg()
            self._conn = psycopg.connect(dsn)
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._conn.commit()

    def _ensure_table(self, dim: int) -> None:
        if self._table_ready:
            return
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS embedsync_chunks (
                    doc_id text,
                    chunk_id text,
                    content text,
                    embedding vector({int(dim)}),
                    primary key (doc_id, chunk_id)
                )
                """
            )
        self._conn.commit()
        self.dim = dim
        self._table_ready = True

    def apply(self, action: SyncAction, embeddings: list[list[float]], dry_run: bool = False) -> None:
        if dry_run:
            return
        if embeddings:
            self._ensure_table(len(embeddings[0]))
        else:
            self._ensure_table(self.dim)

        with self._conn.cursor() as cur:
            if action.action == "delete":
                cur.execute("DELETE FROM embedsync_chunks WHERE doc_id = %s", (action.doc_id,))
            else:
                if action.action == "add":
                    cur.execute(
                        "DELETE FROM embedsync_chunks WHERE doc_id = %s",
                        (action.doc_id,),
                    )
                else:
                    drop = list(action.removed_chunk_ids) + [c.chunk_id for c in action.chunks]
                    if drop:
                        cur.execute(
                            "DELETE FROM embedsync_chunks WHERE doc_id = %s AND chunk_id = ANY(%s)",
                            (action.doc_id, drop),
                        )
                for chunk, vector in zip(action.chunks, embeddings, strict=False):
                    cur.execute(
                        """
                        INSERT INTO embedsync_chunks (doc_id, chunk_id, content, embedding)
                        VALUES (%s, %s, %s, %s::vector)
                        ON CONFLICT (doc_id, chunk_id) DO UPDATE
                        SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
                        """,
                        (action.doc_id, chunk.chunk_id, chunk.content, _vec_literal(vector)),
                    )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
