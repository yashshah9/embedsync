# embedsync

Incremental synchronization between **source documents** and **vector indexes** — detect changes, re-embed only deltas, and delete stale chunks.

[![PyPI](https://img.shields.io/pypi/v/embedsync.svg)](https://pypi.org/project/embedsync/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/yashshah9/embedsync/actions/workflows/ci.yml/badge.svg)](https://github.com/yashshah9/embedsync/actions/workflows/ci.yml)

> **Status:** v0.7 — hash + Ollama + OpenAI embedders, paragraph chunks, JSONL + pgvector + Qdrant destinations, chunk-level re-embed, `--full-reindex`.

## 60-second try

```bash
pip install embedsync
embedsync plan examples/docs --state-db /tmp/embedsync-demo.db
# or with Docker:
docker compose run --rm plan
```

## Why this vs alternatives

| Approach | Strength | Gap |
|----------|----------|-----|
| **embedsync** | Content-hash deltas + pluggable embedders | Destinations: memory, JSONL, pgvector, Qdrant |
| Full re-embed pipelines | Simple mentally | Expensive; misses deletes |
| Framework ingestion (e.g. LlamaIndex) | Rich connectors | Change detection is DIY |
| One-off sync scripts | Fits one repo | No shared plan/state model |

## Problem

RAG indexes rot when documents change. Full re-embeds are expensive and miss deletes. Every team rebuilds change detection from scratch.

## Key features (v0.7)

- Content-hash change detection per document
- Sync plan: add / update / delete actions
- `--full-reindex` to force re-embed of all current docs
- Hash embedder for offline/CI (`--embedder hash`)
- Ollama embedder (`--embedder ollama` or `ollama:nomic-embed-text`)
- OpenAI embedder (`--embedder openai` or `openai:text-embedding-3-small`)
- JSONL, in-memory, pgvector, or Qdrant destination
- Unchanged docs/chunks skip re-embedding on the next run

## Architecture

```
embedsync run ./docs
    ├── LocalFileSource
    ├── StateStore (SQLite)
    ├── plan_sync() → diff
    └── Destination (Memory / JSONL / pgvector / Qdrant)
```

## Installation

```bash
pip install embedsync
pip install 'embedsync[pg]'       # optional: pgvector destination
pip install 'embedsync[qdrant]'   # optional: Qdrant destination
pip install -e ".[dev]"
```

## Usage

```bash
embedsync health
embedsync plan examples/docs --state-db /tmp/embedsync-demo.db
embedsync run examples/docs --dry-run --state-db /tmp/embedsync-demo.db
embedsync run examples/docs --embedder hash --destination memory --state-db /tmp/embedsync-demo.db
embedsync run examples/docs --full-reindex --embedder hash --destination jsonl:/tmp/index.jsonl
embedsync run examples/docs --embedder hash --destination jsonl:/tmp/index.jsonl
# Requires Postgres with pgvector + pip install 'embedsync[pg]':
embedsync run examples/docs --embedder hash --destination pgvector:postgresql://user:pass@localhost/db
# Requires Qdrant + pip install 'embedsync[qdrant]':
embedsync run examples/docs --embedder hash --destination qdrant:http://localhost:6333/embedsync
embedsync run examples/docs --embedder hash --destination 'qdrant:http://localhost:6333#embedsync'
# Requires a running Ollama with an embedding model:
embedsync run examples/docs --embedder ollama --destination jsonl:/tmp/index.jsonl
embedsync run examples/docs --embedder ollama:nomic-embed-text --destination memory
# Requires OPENAI_API_KEY:
embedsync run examples/docs --embedder openai --destination jsonl:/tmp/index.jsonl
embedsync run examples/docs --embedder openai:text-embedding-3-small --destination memory
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
| `OPENAI_API_KEY` | — | Required for `--embedder openai` |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama base URL |
| `QDRANT_API_KEY` | — | Optional API key for Qdrant Cloud |

## Roadmap

- [x] Pluggable embedder protocol + hash backend
- [x] JSONL destination (local stand-in)
- [x] Chunk-level stable IDs across edits
- [x] Ollama embedder (`--embedder ollama`)
- [x] OpenAI embedder (`--embedder openai`)
- [x] pgvector destination
- [x] Qdrant destination
- [ ] Notion and sitemap sources

## License

MIT

## Known limitations (v0.7)

- Hash embeddings are not semantic — use `--embedder ollama` or `--embedder openai` for semantic vectors
- JSONL is not a vector DB; use `--destination pgvector:...` or `qdrant:...` for real stores
- Local markdown files only
- Re-runs reuse `.embedsync/state.db`; pass `--state-db` for an isolated plan
- Ollama must already be running and have the embedding model pulled
- OpenAI needs `OPENAI_API_KEY`
- pgvector destination needs `pip install 'embedsync[pg]'` and the `vector` extension
- Qdrant destination needs `pip install 'embedsync[qdrant]'`
