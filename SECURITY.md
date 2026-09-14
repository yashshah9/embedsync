# Security Policy

## Reporting a vulnerability

Email **yash376351@gmail.com** with the repo name, a short description, and steps to reproduce. Please do not open a public issue for exploitable findings until we have had a reasonable chance to respond.

## Threat model (honest)

embedsync reads local documents, stores sync state in SQLite, and may call a configured embedder (hash, Ollama, or OpenAI).

- It is **not** a vector database security boundary.
- Document content is sent to the embedder you select (`hash` stays local; `ollama` hits your Ollama host; `openai` sends text to OpenAI).
- State DBs and JSONL / vector destinations may contain document text and embeddings — treat them as sensitive if the source corpus is.
- There is no multi-tenant isolation; run one sync workspace per trust domain.
