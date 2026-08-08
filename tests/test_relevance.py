"""Tests for relevance scoring."""

import pytest
from src.config import Config
from src.intelligence.relevance import score_relevance
from src.models import Domain, IntelligenceItem


@pytest.fixture(autouse=True)
def reset_config():
    Config.reset()
    yield
    Config.reset()


def _item(title: str, domain: Domain, summary: str = "") -> IntelligenceItem:
    return IntelligenceItem(
        title=title, url="https://example.com/test",
        domain=domain, summary=summary,
    )


class TestAIRelevance:
    def test_llm_topic_scores_high(self):
        item = _item(
            "New Large Language Model achieves breakthrough",
            Domain.AI_RESEARCH,
            "A novel LLM architecture for reasoning",
        )
        score = score_relevance(item)
        assert score >= 2.5

    def test_agent_topic_scores_high(self):
        item = _item(
            "Agentic AI framework for autonomous tasks",
            Domain.AI_RESEARCH,
        )
        score = score_relevance(item)
        assert score >= 2.5

    def test_low_priority_topic_scores_low(self):
        item = _item(
            "Random forest applied to weather prediction",
            Domain.AI_RESEARCH,
        )
        score = score_relevance(item)
        assert score <= 1.0

    def test_no_keywords_scores_zero(self):
        item = _item("A study on something", Domain.AI_RESEARCH)
        score = score_relevance(item)
        assert score == 0.0


class TestGeopoliticsRelevance:
    def test_military_conflict_scores_high(self):
        item = _item(
            "Russia-Ukraine military escalation continues",
            Domain.GEOPOLITICS,
        )
        score = score_relevance(item)
        assert score >= 1.5

    def test_trade_deal_scores_high(self):
        item = _item(
            "India-EU sign historic trade agreement",
            Domain.GEOPOLITICS,
        )
        score = score_relevance(item)
        assert score >= 1.5

    def test_generic_news_scores_low(self):
        item = _item("Local event in small town", Domain.GEOPOLITICS)
        score = score_relevance(item)
        assert score <= 1.0


class TestMarketRelevance:
    def test_central_bank_scores_high(self):
        item = _item(
            "Federal Reserve announces rate cut",
            Domain.MARKETS,
        )
        score = score_relevance(item)
        assert score >= 2.0

    def test_rbi_decision_scores_high(self):
        item = _item("RBI monetary policy decision", Domain.MARKETS)
        score = score_relevance(item)
        assert score >= 1.5


class TestTechRelevance:
    def test_product_launch_scores_high(self):
        item = _item(
            "NVIDIA launches new AI accelerator chip",
            Domain.TECHNOLOGY,
        )
        score = score_relevance(item)
        assert score >= 2.0

    def test_generic_blog_scores_low(self):
        item = _item(
            "Tips for better coding",
            Domain.TECHNOLOGY,
        )
        score = score_relevance(item)
        assert score <= 1.0
