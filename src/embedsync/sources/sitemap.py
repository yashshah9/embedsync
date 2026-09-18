"""Sitemap URL source — fetch pages listed in a sitemap.xml."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from embedsync.sources.local import SourceDocument

# ponytail: no sitemap-index recursion, no robots.txt, naive HTML→text; upgrade = those later.
_DEFAULT_MAX_PAGES = 50
_FETCH_TIMEOUT = 30
_UA = "embedsync-sitemap/0.8 (+https://github.com/yashshah9/embedsync)"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def _fetch(url: str, *, timeout: float = _FETCH_TIMEOUT) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": _UA})
    with urlopen(req, timeout=timeout) as resp:
        ctype = ""
        if hasattr(resp, "headers"):
            ctype = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        return resp.read(), ctype


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_sitemap_locs(xml_bytes: bytes) -> list[str]:
    """Return <loc> URLs from a urlset sitemap (not sitemapindex)."""
    root = ET.fromstring(xml_bytes)
    if _strip_ns(root.tag) == "sitemapindex":
        raise ValueError(
            "sitemap indexes are not supported yet; point sitemap: at a urlset sitemap.xml"
        )
    locs: list[str] = []
    for el in root.iter():
        if _strip_ns(el.tag) == "loc" and el.text:
            loc = el.text.strip()
            if loc:
                locs.append(loc)
    return locs


def html_to_text(raw: bytes, content_type: str = "") -> str:
    if content_type.startswith("text/plain"):
        return raw.decode("utf-8", errors="replace")
    # Heuristic: treat as HTML unless clearly plain
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw.decode("latin-1", errors="replace")
    if content_type.startswith("text/html") or "<html" in decoded[:500].lower() or "<body" in decoded[:2000].lower():
        parser = _TextExtractor()
        parser.feed(decoded)
        text = parser.text()
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    return decoded.strip()


class SitemapSource:
    """Fetch documents from URLs listed in a sitemap.xml."""

    def __init__(self, sitemap_url: str, *, max_pages: int = _DEFAULT_MAX_PAGES) -> None:
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        self.sitemap_url = sitemap_url
        self.max_pages = max_pages

    def list_documents(self) -> list[SourceDocument]:
        try:
            raw, _ = _fetch(self.sitemap_url)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ValueError(f"failed to fetch sitemap {self.sitemap_url}: {exc}") from exc

        try:
            locs = parse_sitemap_locs(raw)
        except ET.ParseError as exc:
            raise ValueError(f"invalid sitemap XML: {exc}") from exc

        docs: list[SourceDocument] = []
        for url in locs[: self.max_pages]:
            try:
                body, ctype = _fetch(url)
            except (HTTPError, URLError, TimeoutError, OSError):
                # ponytail: skip failed pages rather than failing the whole sync
                continue
            content = html_to_text(body, ctype)
            if not content:
                continue
            docs.append(
                SourceDocument(
                    doc_id=url,
                    content=content,
                    metadata={"url": url, "source": "sitemap"},
                )
            )
        return docs


def parse_sitemap_spec(spec: str) -> str:
    """Parse ``sitemap:URL`` into the sitemap URL."""
    if not spec.startswith("sitemap:"):
        raise ValueError("sitemap spec must start with 'sitemap:'")
    url = spec[len("sitemap:") :].strip()
    if not url:
        raise ValueError("sitemap: requires a URL")
    return url
