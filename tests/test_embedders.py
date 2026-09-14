"""Tests for embedders."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from embedsync.embedders import HashEmbedder, OllamaEmbedder, OpenAIEmbedder, resolve_embedder


def test_hash_embedder_is_deterministic() -> None:
    emb = HashEmbedder(dimension=8)
    a = emb.embed(["hello"])[0]
    b = emb.embed(["hello"])[0]
    assert a == b
    assert len(a) == 8


def test_resolve_ollama_model_name() -> None:
    emb = resolve_embedder("ollama:nomic-embed-text")
    assert isinstance(emb, OllamaEmbedder)
    assert emb.model == "nomic-embed-text"


def test_resolve_openai_default_and_model() -> None:
    assert isinstance(resolve_embedder("openai"), OpenAIEmbedder)
    emb = resolve_embedder("openai:text-embedding-3-small")
    assert isinstance(emb, OpenAIEmbedder)
    assert emb.model == "text-embedding-3-small"


def test_ollama_embedder_against_mock_server() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            assert body["model"] == "nomic-embed-text"
            payload = json.dumps({"embedding": [0.1, 0.2, 0.3, 0.4]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address[:2]
        emb = OllamaEmbedder(host=f"http://{host}:{port}", model="nomic-embed-text")
        vectors = emb.embed(["docs"])
        assert vectors == [[0.1, 0.2, 0.3, 0.4]]
        assert emb.dimension == 4
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_openai_embedder_against_mock_server() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            assert self.headers.get("Authorization") == "Bearer test-key"
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            assert body["model"] == "text-embedding-3-small"
            assert body["input"] == ["a", "b"]
            payload = json.dumps(
                {
                    "data": [
                        {"index": 1, "embedding": [0.3, 0.4]},
                        {"index": 0, "embedding": [0.1, 0.2]},
                    ]
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address[:2]
        emb = OpenAIEmbedder(
            api_key="test-key",
            base_url=f"http://{host}:{port}/v1",
            model="text-embedding-3-small",
        )
        vectors = emb.embed(["a", "b"])
        assert vectors == [[0.1, 0.2], [0.3, 0.4]]
        assert emb.dimension == 2
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_openai_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    emb = OpenAIEmbedder(api_key="")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        emb.embed(["x"])
