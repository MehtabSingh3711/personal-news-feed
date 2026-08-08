"""Tests for importance scoring and classification."""

import pytest
from datetime import datetime, timezone, timedelta

from src.config import Config
from src.intelligence.importance import (
    compute_importance,
    classify_items,
    _recency_score,
    _community_score,
    _academic_score,
    _cross_source_bonus,
)
from src.models import Classification, Domain, IntelligenceItem


@pytest.fixture(autouse=True)
def reset_config():
    Config.reset()
    yield
    Config.reset()


def _item(title: str, domain: Domain, **kwargs) -> IntelligenceItem:
    return IntelligenceItem(
        id=f"test_{hash(title) % 10000}",
        title=title,
        url=f"https://example.com/{hash(title) % 10000}",
        domain=domain,
        source_score=kwargs.get("source_score", 0.90),
        **{k: v for k, v in kwargs.items() if k != "source_score"},
    )


class TestRecencyScore:
    def test_recent_item_scores_high(self):
        item = _item("New", Domain.AI_RESEARCH,
                      published_at=datetime.now(timezone.utc))
        config = Config.get()
        score = _recency_score(item, config)
        assert score >= 0.9

    def test_old_item_scores_low(self):
        item = _item("Old", Domain.AI_RESEARCH,
                      published_at=datetime.now(timezone.utc) - timedelta(days=5))
        config = Config.get()
        score = _recency_score(item, config)
        assert score < 0.5

    def test_unknown_date_gets_middle(self):
        item = _item("Unknown", Domain.AI_RESEARCH)
        config = Config.get()
        score = _recency_score(item, config)
        assert score == 0.5


class TestCommunityScore:
    def test_high_upvotes(self):
        item = _item("Popular", Domain.AI_RESEARCH, hf_upvotes=200)
        score = _community_score(item)
        assert score > 0.5

    def test_high_stars(self):
        item = _item("Starred", Domain.AI_RESEARCH, github_stars=5000)
        score = _community_score(item)
        assert score > 0.5

    def test_no_signals(self):
        item = _item("Nothing", Domain.AI_RESEARCH)
        score = _community_score(item)
        assert score == 0.0

    def test_non_research_gets_zero(self):
        item = _item("News", Domain.GEOPOLITICS, hf_upvotes=100)
        score = _community_score(item)
        assert score == 0.0


class TestCrossSourceBonus:
    def test_single_source_no_bonus(self):
        item = _item("Solo", Domain.GEOPOLITICS)
        config = Config.get()
        assert _cross_source_bonus(item, config) == 0.0

    def test_two_sources_small_bonus(self):
        item = _item("Dual", Domain.GEOPOLITICS, cluster_sources=["BBC"])
        config = Config.get()
        bonus = _cross_source_bonus(item, config)
        assert bonus > 0

    def test_three_sources_bigger_bonus(self):
        item = _item("Multi", Domain.GEOPOLITICS,
                      cluster_sources=["BBC", "Reuters"])
        config = Config.get()
        bonus = _cross_source_bonus(item, config)
        assert bonus > 0.3


class TestComputeImportance:
    def test_high_value_ai_paper_scores_well(self):
        items = [
            _item(
                "Novel Large Language Model architecture with breakthrough reasoning",
                Domain.AI_RESEARCH,
                published_at=datetime.now(timezone.utc),
                hf_upvotes=150,
                source_score=0.97,
            ),
        ]
        result = compute_importance(items)
        assert result[0].deterministic_score > 5.0

    def test_geopolitical_crisis_scores_well(self):
        items = [
            _item(
                "India-China military escalation at border",
                Domain.GEOPOLITICS,
                published_at=datetime.now(timezone.utc),
                source_score=0.98,
                cluster_sources=["Reuters", "AP"],
            ),
        ]
        result = compute_importance(items)
        assert result[0].deterministic_score > 5.0


class TestClassification:
    def test_must_read_threshold(self):
        items = [_item("High", Domain.AI_RESEARCH)]
        items[0].final_score = 8.5
        result = classify_items(items)
        assert result[0].classification == Classification.MUST_READ

    def test_worth_knowing_threshold(self):
        items = [_item("Medium", Domain.AI_RESEARCH)]
        items[0].final_score = 7.0
        result = classify_items(items)
        assert result[0].classification == Classification.WORTH_KNOWING

    def test_discarded_threshold(self):
        items = [_item("Low", Domain.AI_RESEARCH)]
        items[0].final_score = 4.0
        result = classify_items(items)
        assert result[0].classification == Classification.DISCARDED
