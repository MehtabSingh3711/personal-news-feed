"""Tests for normalization."""

import pytest
from src.processing.normalization import (
    normalize_title,
    normalize_url,
    extract_arxiv_id,
    extract_doi,
    title_for_comparison,
    normalize_items,
)
from src.models import IntelligenceItem


class TestNormalizeTitle:
    def test_strips_html_entities(self):
        assert normalize_title("AI &amp; ML") == "AI & ML"
        assert normalize_title("It&#39;s here") == "It's here"

    def test_strips_html_tags(self):
        assert normalize_title("<b>Important</b> news") == "Important news"

    def test_strips_breaking_prefix(self):
        assert normalize_title("BREAKING: Major event") == "Major event"
        assert normalize_title("UPDATE: New info") == "New info"

    def test_normalizes_whitespace(self):
        assert normalize_title("  Too   many    spaces  ") == "Too many spaces"


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://example.com/a?utm_source=rss&id=1"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "id=1" in result

    def test_strips_fragment(self):
        url = "https://example.com/a#section"
        result = normalize_url(url)
        assert "#" not in result

    def test_strips_trailing_slash(self):
        url = "https://example.com/article/"
        result = normalize_url(url)
        assert not result.endswith("/")


class TestExtractArxivId:
    def test_extracts_from_url(self):
        item = IntelligenceItem(url="https://arxiv.org/abs/2401.12345")
        assert extract_arxiv_id(item) == "2401.12345"

    def test_extracts_from_pdf_url(self):
        item = IntelligenceItem(url="https://arxiv.org/pdf/2401.12345")
        assert extract_arxiv_id(item) == "2401.12345"

    def test_extracts_from_title(self):
        item = IntelligenceItem(url="https://example.com", title="Paper 2401.12345")
        assert extract_arxiv_id(item) == "2401.12345"

    def test_returns_none_when_absent(self):
        item = IntelligenceItem(url="https://example.com", title="Normal title")
        assert extract_arxiv_id(item) is None


class TestExtractDoi:
    def test_extracts_doi(self):
        item = IntelligenceItem(
            url="https://doi.org/10.1234/test.5678",
            title="Paper"
        )
        assert extract_doi(item) == "10.1234/test.5678"


class TestTitleForComparison:
    def test_case_insensitive(self):
        assert title_for_comparison("Hello World") == title_for_comparison("hello world")

    def test_strips_punctuation(self):
        t1 = title_for_comparison("Attention Is All You Need")
        t2 = title_for_comparison("Attention is all you need.")
        assert t1 == t2

    def test_normalizes_whitespace(self):
        t1 = title_for_comparison("Big  Model")
        t2 = title_for_comparison("Big Model")
        assert t1 == t2


class TestNormalizeItems:
    def test_normalizes_list(self):
        items = [
            IntelligenceItem(
                title="BREAKING: &amp; Test",
                url="https://example.com?utm_source=rss",
                summary="<b>Bold</b> text",
            ),
        ]
        result = normalize_items(items)
        assert result[0].title == "& Test"
        assert "utm_source" not in result[0].url
        assert "<b>" not in (result[0].summary or "")
