# embedsync

Incremental synchronization between **source documents** and **vector indexes** — detect changes, re-embed only deltas, and delete stale chunks.

[![PyPI](https://img.shields.io/pypi/v/embedsync.svg)](https://pypi.org/project/embedsync/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/yashshah9/embedsync/actions/workflows/ci.yml/badge.svg)](https://github.com/yashshah9/embedsync/actions/workflows/ci.yml)

> **Status:** v0.9 — local + sitemap + **Notion** sources, hash/Ollama/OpenAI embedders, JSONL + pgvector + Qdrant.

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

## Key features (v0.8)

- Local markdown directory, `sitemap:URL`, or `notion:` / `notion:query` sources
- Content-hash change detection per document
- Sync plan: add / update / delete actions
- `--full-reindex` to force re-embed of all current docs
- Hash / Ollama / OpenAI embedders
- JSONL, memory, pgvector, or Qdrant destination
- Unchanged docs/chunks skip re-embedding on the next run

## Architecture

```
embedsync run ./docs
embedsync run 'sitemap:https://example.com/sitemap.xml'
embedsync run 'notion:'   # or notion:handbook
    ├── LocalFileSource | SitemapSource | NotionSource
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
# Sitemap (urlset only; --max-pages caps crawl):
embedsync plan 'sitemap:https://example.com/sitemap.xml' --max-pages 20
embedsync run 'sitemap:https://example.com/sitemap.xml' --embedder hash --destination memory
# Notion (integration token; share pages with the integration):
export NOTION_API_KEY=secret_...
embedsync plan 'notion:' --max-pages 20
embedsync run 'notion:handbook' --embedder hash --destination memory
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
| `NOTION_API_KEY` | — | Required for `notion:` sources |
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
- [x] Sitemap source (`sitemap:URL`)
- [x] Notion source (`notion:` / `notion:query`)

## License

MIT

## Known limitations (v0.9)

- Hash embeddings are not semantic — use `--embedder ollama` or `--embedder openai` for semantic vectors
- JSONL is not a vector DB; use `--destination pgvector:...` or `qdrant:...` for real stores
- Sitemap: urlset only (no sitemap-index recursion); failed page fetches are skipped
- Notion: Search API pages only (no database queries); shallow block recursion; needs pages shared with the integration
- Re-runs reuse `.embedsync/state.db`; pass `--state-db` for an isolated plan
- Ollama must already be running and have the embedding model pulled
- OpenAI needs `OPENAI_API_KEY`
- pgvector destination needs `pip install 'embedsync[pg]'` and the `vector` extension
- Qdrant destination needs `pip install 'embedsync[qdrant]'`
