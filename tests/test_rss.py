"""Tests for RSS output generation."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from xml.etree.ElementTree import parse as xml_parse

from src.output.rss import generate_feed
from src.output.formatter import format_title, format_description
from src.models import Classification, Domain, IntelligenceItem


def _item(title: str, score: float, classification: Classification, **kwargs) -> IntelligenceItem:
    return IntelligenceItem(
        id=f"test_{hash(title) % 10000}",
        title=title,
        url=f"https://example.com/{hash(title) % 10000}",
        domain=kwargs.get("domain", Domain.AI_RESEARCH),
        final_score=score,
        classification=classification,
        published_at=datetime.now(timezone.utc),
        source="TestSource",
        summary=kwargs.get("summary", "Test summary"),
        categories=kwargs.get("categories", ["AI Research"]),
    )


class TestFormatTitle:
    def test_includes_score(self):
        item = _item("Test Title", 9.4, Classification.MUST_READ)
        title = format_title(item)
        assert "[9.4]" in title
        assert "Test Title" in title


class TestFormatDescription:
    def test_includes_sections(self):
        item = _item(
            "Test", 8.5, Classification.MUST_READ,
            summary="Important development",
            categories=["AI Research", "LLM"],
        )
        desc = format_description(item)
        assert "WHAT HAPPENED" in desc
        assert "IMPORTANCE" in desc
        assert "CATEGORY" in desc
        assert "8.5/10" in desc

    def test_escapes_html(self):
        item = _item("Test", 7.0, Classification.WORTH_KNOWING,
                      summary="<b>bold</b> text")
        desc = format_description(item)
        assert "<b>" not in desc

    def test_shows_signals(self):
        item = _item("Test", 8.0, Classification.MUST_READ)
        item.hf_upvotes = 150
        item.github_stars = 2000
        desc = format_description(item)
        assert "SIGNALS" in desc
        assert "150 upvotes" in desc
        assert "2,000 ★" in desc


class TestGenerateFeed:
    def test_generates_valid_xml(self):
        items = [
            _item("Must Read Item", 9.0, Classification.MUST_READ),
            _item("Worth Knowing", 7.0, Classification.WORTH_KNOWING),
            _item("Discarded", 4.0, Classification.DISCARDED),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feed.xml"
            result = generate_feed(items, path)
            assert result.exists()

            # Parse XML to verify validity
            tree = xml_parse(str(path))
            root = tree.getroot()
            assert root.tag == "rss"

            # Should have 2 items (discarded excluded)
            channel = root.find("channel")
            rss_items = channel.findall("item")
            assert len(rss_items) == 2

    def test_sorted_by_score(self):
        items = [
            _item("Lower", 7.0, Classification.WORTH_KNOWING),
            _item("Higher", 9.0, Classification.MUST_READ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feed.xml"
            generate_feed(items, path)

            tree = xml_parse(str(path))
            channel = tree.getroot().find("channel")
            rss_items = channel.findall("item")
            titles = [item.find("title").text for item in rss_items]
            assert "Higher" in titles[0]

    def test_has_guid(self):
        items = [_item("Test", 8.0, Classification.MUST_READ)]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feed.xml"
            generate_feed(items, path)

            tree = xml_parse(str(path))
            channel = tree.getroot().find("channel")
            guid = channel.find("item/guid")
            assert guid is not None
            assert guid.text is not None

    def test_empty_feed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feed.xml"
            result = generate_feed([], path)
            assert result.exists()
