# Contributing

## Running tests

Prefer Docker Compose:

```bash
docker compose run --rm test
docker compose run --rm plan
```

Locally:

```bash
pip install -e ".[dev]"
pytest tests/ -v
embedsync plan examples/docs --state-db /tmp/embedsync-demo.db
embedsync run examples/docs --dry-run --state-db /tmp/embedsync-demo.db
```

## Pull requests

- Keep embedder changes covered by unit tests (mock Ollama where needed)
- Update README/CHANGELOG for new destinations or CLI flags
- Prefer small PRs with a clear test plan

## Commit style

- Imperative subject line; mention the user-facing why when relevant
- Do not add AI co-author trailers (e.g. Co-authored-by: Cursor) to commits.
