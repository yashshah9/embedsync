"""Tests for Notion source (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from embedsync.sources.notion import (
    NotionSource,
    block_plain_text,
    page_title,
    parse_notion_spec,
)
from embedsync.state.store import StateStore
from embedsync.sync.engine import plan_sync


def test_parse_notion_spec() -> None:
    assert parse_notion_spec("notion:") == ""
    assert parse_notion_spec("notion:handbook") == "handbook"
    with pytest.raises(ValueError):
        parse_notion_spec("notion")


def test_page_title_and_block_text() -> None:
    page = {
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "Hello"}]}
        }
    }
    assert page_title(page) == "Hello"
    block = {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": "World"}]},
    }
    assert block_plain_text(block) == "World"


def test_notion_source_list_documents() -> None:
    calls: list[tuple[str, str]] = []

    def fake_http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict[str, Any]:
        calls.append((method, url))
        assert headers["Authorization"] == "Bearer secret-token"
        assert headers["Notion-Version"] == "2022-06-28"
        if url.endswith("/search"):
            payload = json.loads(body or b"{}")
            assert payload.get("filter", {}).get("value") == "page"
            return {
                "results": [
                    {
                        "object": "page",
                        "id": "page-1",
                        "url": "https://notion.so/page-1",
                        "properties": {
                            "title": {
                                "type": "title",
                                "title": [{"plain_text": "Doc One"}],
                            }
                        },
                    }
                ],
                "has_more": False,
                "next_cursor": None,
            }
        if "/blocks/page-1/children" in url:
            return {
                "results": [
                    {
                        "object": "block",
                        "id": "b1",
                        "type": "paragraph",
                        "has_children": False,
                        "paragraph": {"rich_text": [{"plain_text": "Hello from Notion."}]},
                    }
                ],
                "has_more": False,
                "next_cursor": None,
            }
        raise AssertionError(f"unexpected {method} {url}")

    src = NotionSource(token="secret-token", http=fake_http, max_pages=10)
    docs = src.list_documents()
    assert len(docs) == 1
    assert docs[0].doc_id == "page-1"
    assert "Doc One" in docs[0].content
    assert "Hello from Notion." in docs[0].content
    assert docs[0].metadata["source"] == "notion"
    assert any(u.endswith("/search") for _, u in calls)


def test_notion_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NOTION_API_KEY"):
        NotionSource(token="")


def test_notion_plan_sync(tmp_path: Path) -> None:
    def fake_http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict[str, Any]:
        if url.endswith("/search"):
            return {
                "results": [
                    {
                        "object": "page",
                        "id": "p2",
                        "url": "https://notion.so/p2",
                        "properties": {
                            "title": {"type": "title", "title": [{"plain_text": "Plan"}]}
                        },
                    }
                ],
                "has_more": False,
            }
        return {
            "results": [
                {
                    "id": "b",
                    "type": "paragraph",
                    "has_children": False,
                    "paragraph": {"rich_text": [{"plain_text": "Body"}]},
                }
            ],
            "has_more": False,
        }

    src = NotionSource(token="t", http=fake_http)
    store = StateStore(str(tmp_path / "state.db"))
    plan = plan_sync(src, store)
    assert len(plan.adds) == 1
    assert plan.adds[0].doc_id == "p2"
    store.close()
