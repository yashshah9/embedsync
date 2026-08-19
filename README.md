# embedsync

Incremental synchronization between **source documents** and **vector indexes** — detect changes, re-embed only deltas, and delete stale chunks.

> **Status:** v0.3 — hash embeddings, paragraph chunks, JSONL destination, chunk-level re-embed.

## Problem

RAG indexes rot when documents change. Full re-embeds are expensive and miss deletes. Every team rebuilds change detection from scratch.

## Key features (v0.2)

- Content-hash change detection per document
- Sync plan: add / update / delete actions
- Hash embedder for offline/CI (`--embedder hash`)
- JSONL or in-memory destination
- Unchanged docs skip re-embedding on the next run

## Architecture

```
embedsync run ./docs
    ├── LocalFileSource
    ├── StateStore (SQLite)
    ├── plan_sync() → diff
    └── Destination (Memory → pgvector next)
```

## Installation

```bash
pip install embedsync
pip install -e ".[dev]"
```

## Usage

```bash
embedsync health
embedsync plan examples/docs --state-db /tmp/embedsync-demo.db
embedsync run examples/docs --dry-run --state-db /tmp/embedsync-demo.db
embedsync run examples/docs --embedder hash --destination memory --state-db /tmp/embedsync-demo.db
embedsync run examples/docs --embedder hash --destination jsonl:/tmp/index.jsonl
```

## Docker

```bash
docker compose run --rm test
docker compose run --rm plan
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDSYNC_STATE_DB` | `.embedsync/state.db` | State database path |
| `EMBEDSYNC_LOG_LEVEL` | `INFO` | Log level |

## Roadmap

- [x] Pluggable embedder protocol + hash backend
- [x] JSONL destination (local stand-in)
- [x] Chunk-level stable IDs across edits
- [ ] pgvector and Qdrant destinations
- [ ] Notion and sitemap sources

## License

MIT

## Known limitations (v0.3)

- Hash embeddings are not semantic — OpenAI/Ollama come later
- JSONL is not a vector DB
- Local markdown files only
- Re-runs reuse `.embedsync/state.db`; pass `--state-db` for an isolated plan
