"""Tests for deduplication."""

import pytest
from src.processing.deduplication import deduplicate
from src.models import IntelligenceItem


def _item(title: str, url: str, **kwargs) -> IntelligenceItem:
    return IntelligenceItem(
        id=f"test_{hash(url) % 10000}",
        title=title,
        url=url,
        source_score=kwargs.get("source_score", 0.90),
        source=kwargs.get("source", "TestSource"),
        **{k: v for k, v in kwargs.items() if k not in ("source_score", "source")},
    )


class TestDeduplication:
    def test_doi_dedup(self):
        items = [
            _item("Paper A", "https://a.com", doi="10.1234/test"),
            _item("Paper A Copy", "https://b.com", doi="10.1234/test"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_arxiv_dedup(self):
        items = [
            _item("Paper", "https://arxiv.org/abs/2401.12345", arxiv_id="2401.12345"),
            _item("Same Paper", "https://hf.co/papers/2401.12345", arxiv_id="2401.12345"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_url_dedup(self):
        items = [
            _item("Article", "https://example.com/article"),
            _item("Article", "https://example.com/article"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_title_similarity_dedup(self):
        items = [
            _item("Attention Is All You Need", "https://a.com/1"),
            _item("Attention is all you need.", "https://b.com/2"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_different_items_kept(self):
        items = [
            _item("NVIDIA launches GPU", "https://a.com/1"),
            _item("Apple releases new chip", "https://b.com/2"),
        ]
        result = deduplicate(items)
        assert len(result) == 2

    def test_keeps_higher_quality_source(self):
        items = [
            _item("Story", "https://a.com/1", source_score=0.70, source="LowQuality"),
            _item("Story", "https://a.com/1", source_score=0.98, source="Reuters"),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0].source == "Reuters"

    def test_merges_enrichment_data(self):
        items = [
            _item("Paper", "https://a.com/1", source_score=0.95, hf_upvotes=100),
            _item("Paper", "https://a.com/1", source_score=0.90, github_stars=500),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0].hf_upvotes == 100
        assert result[0].github_stars == 500

    def test_tracks_cluster_sources(self):
        items = [
            _item("Story", "https://a.com/1", source="Reuters", source_score=0.99),
            _item("Story", "https://a.com/1", source="BBC", source_score=0.93),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert "BBC" in result[0].cluster_sources
