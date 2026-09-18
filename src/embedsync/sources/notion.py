"""Notion workspace source — pages shared with an integration."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from embedsync.sources.local import SourceDocument

# ponytail: search+block children only, shallow recursion, no databases/comments;
# upgrade = database queries, incremental --since, richer markdown.
_API = "https://api.notion.com/v1"
_VERSION = "2022-06-28"
_DEFAULT_MAX_PAGES = 50
_MAX_BLOCK_DEPTH = 3
_TIMEOUT = 30

HttpFn = Callable[[str, str, dict[str, str], bytes | None], dict[str, Any]]


def _default_http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict[str, Any]:
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"Notion API HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Notion API request failed: {exc}") from exc


def _rich_plain(rich: list[dict[str, Any]] | None) -> str:
    if not rich:
        return ""
    return "".join(str(part.get("plain_text") or "") for part in rich)


def page_title(page: dict[str, Any]) -> str:
    props = page.get("properties") or {}
    for prop in props.values():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") == "title":
            return _rich_plain(prop.get("title")) or "Untitled"
    return "Untitled"


def block_plain_text(block: dict[str, Any]) -> str:
    btype = block.get("type")
    if not btype or not isinstance(block.get(btype), dict):
        return ""
    payload = block[btype]
    if "rich_text" in payload:
        return _rich_plain(payload.get("rich_text"))
    if btype == "code":
        return _rich_plain(payload.get("rich_text"))
    if btype in {"bulleted_list_item", "numbered_list_item", "to_do", "toggle", "quote", "callout"}:
        return _rich_plain(payload.get("rich_text"))
    if btype == "child_page":
        return str(payload.get("title") or "")
    return ""


def parse_notion_spec(spec: str) -> str:
    """Parse ``notion:`` or ``notion:search query`` → search query (may be empty)."""
    if not spec.startswith("notion:"):
        raise ValueError("notion spec must start with 'notion:'")
    return spec[len("notion:") :].strip()


class NotionSource:
    """List Notion pages via Search API and flatten block text."""

    def __init__(
        self,
        *,
        token: str | None = None,
        query: str = "",
        max_pages: int = _DEFAULT_MAX_PAGES,
        http: HttpFn | None = None,
    ) -> None:
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        self.token = token or os.environ.get("NOTION_API_KEY", "")
        if not self.token:
            raise ValueError("NOTION_API_KEY is required for notion: sources")
        self.query = query
        self.max_pages = max_pages
        self._http = http or _default_http
        self.last_list_incomplete = False

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": _VERSION,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._http(
            "POST",
            f"{_API}{path}",
            self._headers(),
            json.dumps(payload).encode("utf-8"),
        )

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{_API}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        return self._http("GET", url, self._headers(), None)

    def _search_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor: str | None = None
        truncated = False
        while len(pages) < self.max_pages:
            body: dict[str, Any] = {
                "page_size": min(100, self.max_pages - len(pages)),
                "filter": {"value": "page", "property": "object"},
            }
            if self.query:
                body["query"] = self.query
            if cursor:
                body["start_cursor"] = cursor
            data = self._post("/search", body)
            batch = [i for i in (data.get("results") or []) if i.get("object") == "page"]
            for item in batch:
                if len(pages) >= self.max_pages:
                    truncated = True
                    break
                pages.append(item)
            if truncated:
                break
            if len(pages) >= self.max_pages and data.get("has_more"):
                truncated = True
                break
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break
        if truncated:
            self.last_list_incomplete = True
        return pages

    def _block_children(self, block_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, str] = {"page_size": "100"}
            if cursor:
                params["start_cursor"] = cursor
            data = self._get(f"/blocks/{block_id}/children", params)
            results.extend(data.get("results") or [])
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break
        return results

    def _blocks_to_text(self, block_id: str, *, depth: int = 0) -> str:
        if depth > _MAX_BLOCK_DEPTH:
            return ""
        lines: list[str] = []
        for block in self._block_children(block_id):
            text = block_plain_text(block).strip()
            if text:
                lines.append(text)
            if block.get("has_children"):
                child = self._blocks_to_text(str(block["id"]), depth=depth + 1)
                if child:
                    lines.append(child)
        return "\n".join(lines)

    def list_documents(self) -> list[SourceDocument]:
        self.last_list_incomplete = False
        docs: list[SourceDocument] = []
        for page in self._search_pages():
            page_id = str(page.get("id") or "")
            if not page_id:
                continue
            title = page_title(page)
            try:
                body = self._blocks_to_text(page_id)
            except ValueError:
                # Skip unreadable pages, but mark incomplete so sync won't DELETE them.
                self.last_list_incomplete = True
                continue
            content = f"# {title}\n\n{body}".strip()
            if not body and title == "Untitled":
                continue
            docs.append(
                SourceDocument(
                    doc_id=page_id,
                    content=content,
                    metadata={
                        "source": "notion",
                        "title": title,
                        "url": str(page.get("url") or ""),
                    },
                )
            )
        return docs
