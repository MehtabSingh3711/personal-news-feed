"""Tests for story clustering."""

import pytest
from datetime import datetime, timezone, timedelta
from src.processing.clustering import cluster_stories, _extract_entities, _entity_similarity
from src.models import Domain, IntelligenceItem


def _item(title: str, domain: Domain = Domain.GEOPOLITICS, **kwargs) -> IntelligenceItem:
    return IntelligenceItem(
        id=f"test_{hash(title) % 10000}",
        title=title,
        url=f"https://example.com/{hash(title) % 10000}",
        domain=domain,
        source=kwargs.get("source", "TestSource"),
        source_score=kwargs.get("source_score", 0.90),
        published_at=kwargs.get("published_at"),
        summary=kwargs.get("summary"),
    )


class TestEntityExtraction:
    def test_extracts_countries(self):
        entities = _extract_entities("India and China reach agreement")
        assert "india" in entities
        assert "china" in entities

    def test_extracts_companies(self):
        entities = _extract_entities("NVIDIA launches new GPU")
        assert "nvidia" in entities

    def test_extracts_institutions(self):
        entities = _extract_entities("RBI announces rate cut")
        assert "rbi" in entities


class TestEntitySimilarity:
    def test_identical_sets(self):
        a = {"india", "china"}
        assert _entity_similarity(a, a) == 1.0

    def test_disjoint_sets(self):
        a = {"india", "china"}
        b = {"usa", "russia"}
        assert _entity_similarity(a, b) == 0.0

    def test_partial_overlap(self):
        a = {"india", "china", "usa"}
        b = {"india", "china", "russia"}
        sim = _entity_similarity(a, b)
        assert 0.4 < sim < 0.6  # 2/4 = 0.5

    def test_empty_sets(self):
        assert _entity_similarity(set(), set()) == 0.0


class TestClusterStories:
    def test_same_event_clustered(self):
        now = datetime.now(timezone.utc)
        items = [
            _item(
                "India and EU conclude landmark trade negotiations",
                source="Reuters", source_score=0.99,
                published_at=now,
                summary="India and the European Union have concluded trade talks",
            ),
            _item(
                "India-EU trade deal talks reach breakthrough",
                source="Economic Times", source_score=0.87,
                published_at=now - timedelta(hours=2),
                summary="India and EU trade deal negotiations breakthrough",
            ),
            _item(
                "India and EU make progress on trade agreement",
                source="The Hindu", source_score=0.92,
                published_at=now - timedelta(hours=1),
                summary="India EU trade agreement progress reported",
            ),
        ]
        result = cluster_stories(items)
        # Should be merged into 1 or 2 clusters (depending on TF-IDF threshold)
        assert len(result) <= 2

    def test_different_events_not_clustered(self):
        now = datetime.now(timezone.utc)
        items = [
            _item(
                "NVIDIA launches new GPU architecture",
                Domain.TECHNOLOGY,
                source="NVIDIA", published_at=now,
                summary="NVIDIA has announced new GPU",
            ),
            _item(
                "Fed signals major monetary policy shift",
                Domain.MARKETS,
                source="Reuters", published_at=now,
                summary="Federal Reserve monetary policy change",
            ),
        ]
        result = cluster_stories(items)
        assert len(result) == 2

    def test_single_item_unchanged(self):
        items = [_item("Standalone article")]
        result = cluster_stories(items)
        assert len(result) == 1
        assert result[0].title == "Standalone article"

    def test_empty_input(self):
        assert cluster_stories([]) == []

    def test_cluster_preserves_best_source(self):
        now = datetime.now(timezone.utc)
        items = [
            _item(
                "India EU trade deal", source="LowQ", source_score=0.70,
                published_at=now,
                summary="India EU trade deal reached",
            ),
            _item(
                "India EU trade deal breakthrough", source="Reuters", source_score=0.99,
                published_at=now,
                summary="India EU trade deal reached breakthrough",
            ),
        ]
        result = cluster_stories(items)
        if len(result) == 1:
            assert result[0].source == "Reuters"
