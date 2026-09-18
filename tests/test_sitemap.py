"""Tests for sitemap source."""

from __future__ import annotations

from pathlib import Path

import pytest

from embedsync.sources.sitemap import (
    SitemapSource,
    html_to_text,
    parse_sitemap_locs,
    parse_sitemap_spec,
)
from embedsync.state.store import StateStore
from embedsync.sync.engine import execute_sync, plan_sync


def test_parse_sitemap_spec() -> None:
    assert parse_sitemap_spec("sitemap:https://ex.com/sitemap.xml") == "https://ex.com/sitemap.xml"
    with pytest.raises(ValueError):
        parse_sitemap_spec("https://ex.com/sitemap.xml")


def test_parse_sitemap_locs() -> None:
    xml = b"""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
      <url><loc>https://example.com/b</loc></url>
    </urlset>
    """
    assert parse_sitemap_locs(xml) == ["https://example.com/a", "https://example.com/b"]


def test_parse_sitemap_index_rejected() -> None:
    xml = b"""<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/s1.xml</loc></sitemap>
    </sitemapindex>
    """
    with pytest.raises(ValueError, match="indexes"):
        parse_sitemap_locs(xml)


def test_html_to_text_strips_scripts() -> None:
    raw = b"<html><head><script>evil()</script></head><body><h1>Hi</h1><p>There</p></body></html>"
    text = html_to_text(raw, "text/html")
    assert "Hi" in text and "There" in text
    assert "evil" not in text


def test_sitemap_source_file_urls(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text("<html><body><h1>Hello sitemap</h1><p>Body copy.</p></body></html>", encoding="utf-8")
    sm = tmp_path / "sitemap.xml"
    page_url = page.resolve().as_uri()
    sm.write_text(
        f"""<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>{page_url}</loc></url>
        </urlset>
        """,
        encoding="utf-8",
    )
    docs = SitemapSource(sm.resolve().as_uri(), max_pages=10).list_documents()
    assert len(docs) == 1
    assert docs[0].doc_id == page_url
    assert "Hello sitemap" in docs[0].content
    assert docs[0].metadata["source"] == "sitemap"


def test_sitemap_plan_and_sync(tmp_path: Path) -> None:
    page = tmp_path / "doc.html"
    page.write_text("<html><body><p>Sync me from sitemap.</p></body></html>", encoding="utf-8")
    sm = tmp_path / "sitemap.xml"
    page_url = page.resolve().as_uri()
    sm.write_text(
        f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{page_url}</loc></url></urlset>",
        encoding="utf-8",
    )
    source = SitemapSource(sm.resolve().as_uri())
    store = StateStore(str(tmp_path / "state.db"))
    plan = plan_sync(source, store)
    assert len(plan.adds) == 1
    report = execute_sync(source, store, dry_run=False)
    assert report.embeddings_written >= 1
    store.close()
