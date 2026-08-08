"""Tests for RSS ingestion."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.ingestion.rss import fetch_feed, _clean_url, _generate_item_id
from src.models import Domain, SourceConfig, SourceType, Priority


# ── Mock RSS Feed ─────────────────────────────────────────
MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>NVIDIA launches new GPU architecture</title>
      <link>https://example.com/nvidia-gpu?utm_source=rss&amp;ref=home</link>
      <description>&lt;p&gt;NVIDIA has announced a major new GPU.&lt;/p&gt;</description>
      <pubDate>Fri, 08 Aug 2025 10:00:00 +0000</pubDate>
      <category>Technology</category>
    </item>
    <item>
      <title>India-EU trade deal breakthrough</title>
      <link>https://example.com/india-eu</link>
      <description>Major trade agreement reached.</description>
      <pubDate>Fri, 08 Aug 2025 09:00:00 +0000</pubDate>
    </item>
    <item>
      <title></title>
      <link></link>
    </item>
  </channel>
</rss>"""


MOCK_MALFORMED = """<?xml version="1.0"?>
<rss><channel><title>Bad</title>
<item><title>Test</title></channel></rss>"""


def _make_source(**kwargs) -> SourceConfig:
    defaults = {
        "name": "Test Source",
        "url": "https://example.com/feed",
        "type": "news",
        "priority": "high",
        "quality_score": 0.90,
    }
    defaults.update(kwargs)
    return SourceConfig(**defaults)


class TestCleanUrl:
    def test_strips_tracking_params(self):
        url = "https://example.com/article?utm_source=rss&utm_medium=feed&id=123"
        cleaned = _clean_url(url)
        assert "utm_source" not in cleaned
        assert "utm_medium" not in cleaned
        assert "id=123" in cleaned

    def test_preserves_clean_urls(self):
        url = "https://example.com/article?id=123"
        assert _clean_url(url) == url

    def test_handles_no_params(self):
        url = "https://example.com/article"
        assert _clean_url(url) == url


class TestGenerateItemId:
    def test_stable_ids(self):
        id1 = _generate_item_id("https://example.com/a", "Title")
        id2 = _generate_item_id("https://example.com/a", "Title")
        assert id1 == id2

    def test_different_urls_different_ids(self):
        id1 = _generate_item_id("https://example.com/a", "Title")
        id2 = _generate_item_id("https://example.com/b", "Title")
        assert id1 != id2


class TestFetchFeed:
    @patch("src.ingestion.rss.requests.get")
    def test_parses_valid_feed(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = MOCK_RSS.encode()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        source = _make_source()
        items = fetch_feed(source, Domain.TECHNOLOGY)

        # Should get 2 items (3rd has no title/link)
        assert len(items) == 2
        assert "NVIDIA" in items[0].title
        assert items[0].domain == Domain.TECHNOLOGY
        assert "utm_source" not in items[0].url

    @patch("src.ingestion.rss.requests.get")
    def test_handles_network_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")

        source = _make_source()
        items = fetch_feed(source, Domain.GEOPOLITICS)
        assert items == []

    @patch("src.ingestion.rss.requests.get")
    def test_handles_malformed_feed(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = MOCK_MALFORMED.encode()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        source = _make_source()
        items = fetch_feed(source, Domain.GEOPOLITICS)
        # feedparser is lenient, should still parse the one item
        assert isinstance(items, list)

    @patch("src.ingestion.rss.requests.get")
    def test_strips_html_from_summary(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = MOCK_RSS.encode()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        source = _make_source()
        items = fetch_feed(source, Domain.TECHNOLOGY)
        # Summary should be plain text, no HTML tags
        if items[0].summary:
            assert "<p>" not in items[0].summary
