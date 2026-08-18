# embedsync

Incremental synchronization between **source documents** and **vector indexes** — detect changes, re-embed only deltas, and delete stale chunks.

> **Status:** v0.1 foundation — local markdown source, SQLite state, in-memory destination; pgvector/Qdrant and embedding integration are next.

## Problem

RAG indexes rot when documents change. Full re-embeds are expensive and miss deletes. Every team rebuilds change detection from scratch.

## Key features (v0.1)

- Content-hash change detection per document
- Sync plan: add / update / delete actions
- SQLite state store (no extra infrastructure)
- Local markdown file source
- `--dry-run` mode

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
embedsync plan examples/docs
embedsync run examples/docs --dry-run
embedsync run examples/docs
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

- [ ] pgvector and Qdrant destinations
- [ ] Pluggable embedding function
- [ ] Chunk-level stable IDs across edits
- [ ] Notion and sitemap sources

## License

MIT

## Known limitations (v0.1)

- Local markdown files only
- In-memory destination (no real vector DB yet)
- Naive fixed-size chunk count heuristic
- No embedding API calls
