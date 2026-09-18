# Changelog

## [0.9.0] - 2026-09-18

### Added
- Notion source: `embedsync plan 'notion:'` or `notion:search query` (needs `NOTION_API_KEY`)
- Stdlib Notion Search + block-children → plain text (no SDK)

## [0.8.0] - 2026-09-18

### Added
- Sitemap source: `embedsync plan 'sitemap:https://example.com/sitemap.xml'` (stdlib fetch + HTML→text)
- `--max-pages` for sitemap crawls (default 50)
- `Source` protocol; sync engine accepts any `list_documents()` provider

## [0.7.0] - 2026-09-14

### Added
- OpenAI embedder (`--embedder openai` or `openai:text-embedding-3-small`; needs `OPENAI_API_KEY`)
- Qdrant destination (`--destination qdrant:http://host:6333/collection` or `qdrant:URL#collection`)
- Optional extra: `pip install 'embedsync[qdrant]'` (`qdrant-client>=1.9`)

## [0.6.0] - 2026-09-14

### Added
- pgvector destination (`--destination pgvector:DSN` or `postgresql://...` / `postgres://...`)
- Optional extra: `pip install 'embedsync[pg]'` (`psycopg[binary]>=3.1`)

## [0.5.0] - 2026-09-14

### Added
- `--full-reindex` on `run` / `plan`: force re-embed all current docs (ignore content-hash equality); removed docs still DELETE

## [0.4.0] - 2026-09-14

### Added
- Ollama embedder via `--embedder ollama` or `--embedder ollama:<model>` (default model `nomic-embed-text`)

## [0.3.0] - 2026-08-19

### Added
- Chunk-level re-embed: unchanged chunks are skipped on document edit
- SQLite `chunks` table in the state store

## [0.2.0] - 2026-08-19

### Added
- Hash embedder for offline/CI runs (`--embedder hash`)
- Paragraph chunking with stable-ish chunk IDs
- JSONL destination (`--destination jsonl:/path`)
- Unchanged documents write 0 embeddings on the second run

### Notes
- Real pgvector/Qdrant destinations are still open

## [0.1.0] - 2026-08-18

### Added
- Local markdown source, SQLite state store, sync plan engine
- Memory destination stub and dry-run mode
