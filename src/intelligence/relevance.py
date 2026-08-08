"""Domain-aware relevance scoring.

Each domain uses its own relevance logic:
- AI Research → topic weight matching, methodology vs application detection
- Geopolitics → strategic significance, material change detection
- Markets → event magnitude, policy impact
- Technology → event type classification, product vs marketing
"""

from __future__ import annotations

import math
import re

from src.config import Config
from src.models import Domain, IntelligenceItem


def score_relevance(item: IntelligenceItem) -> float:
    """Score relevance (0-3) based on domain-specific criteria."""
    config = Config.get()

    if item.domain == Domain.AI_RESEARCH:
        return _score_ai_relevance(item, config)
    elif item.domain == Domain.GEOPOLITICS:
        return _score_geopolitics_relevance(item, config)
    elif item.domain == Domain.INDIA:
        return _score_india_relevance(item, config)
    elif item.domain == Domain.MARKETS:
        return _score_market_relevance(item, config)
    elif item.domain == Domain.TECHNOLOGY:
        return _score_technology_relevance(item, config)
    elif item.domain == Domain.GITHUB:
        return _score_github_relevance(item, config)

    return 1.0  # Default


def _score_github_relevance(item: IntelligenceItem, config: Config) -> float:
    """Score GitHub repository relevance (0-3)."""
    text = f"{item.title} {item.summary or ''} {' '.join(item.categories)}".lower()
    score = 1.0

    if any(k in text for k in ["llm", "large language", "agent", "agents", "rag", "multimodal"]):
        score += 1.5
    elif any(k in text for k in ["deep learning", "neural", "transformer", "diffusion", "vllm", "inference"]):
        score += 1.0

    if item.paper_url or item.arxiv_id:
        score += 0.5

    return min(score, 3.0)


def _score_ai_relevance(item: IntelligenceItem, config: Config) -> float:
    """Score AI research relevance using topic weights.

    Does NOT just count keywords — uses best-match topic scoring.
    """
    text = f"{item.title} {item.summary or ''}".lower()
    max_weight = 0.0

    for priority_level in ["very_high", "medium", "low"]:
        topics = config.ai_topics.get(priority_level, [])
        for topic in topics:
            keyword = topic["keyword"].lower()
            aliases = [a.lower() for a in topic.get("aliases", [])]
            weight = topic.get("weight", 1.0)

            all_terms = [keyword] + aliases
            for term in all_terms:
                if term in text:
                    max_weight = max(max_weight, weight)
                    break

    # Cap at 3.0
    return min(max_weight, 3.0)


def _score_geopolitics_relevance(item: IntelligenceItem, config: Config) -> float:
    """Score geopolitical relevance based on strategic significance."""
    text = f"{item.title} {item.summary or ''}".lower()
    score = 0.0

    # Check priority regions
    regions = config.geopolitics_config.get("high_priority_regions", [])
    for region in regions:
        if region.lower() in text:
            score += 1.0
            break

    # Check priority event types
    events = config.geopolitics_config.get("high_priority_events", [])
    event_hits = sum(1 for e in events if e.lower() in text)
    score += min(event_hits * 0.5, 1.5)

    # Material change detection
    change_words = [
        "breakthrough", "landmark", "historic", "unprecedented", "major",
        "crisis", "escalat", "collapse", "agrees", "signs", "declares",
        "invades", "withdraw", "deploys", "suspends", "bans",
    ]
    if any(w in text for w in change_words):
        score += 0.5

    return min(score, 3.0)


def _score_india_relevance(item: IntelligenceItem, config: Config) -> float:
    """Score Indian news relevance — national/economic significance."""
    text = f"{item.title} {item.summary or ''}".lower()
    score = 0.0

    # Major institutional events
    major_institutions = [
        "supreme court", "rbi", "reserve bank", "sebi", "parliament",
        "lok sabha", "rajya sabha", "prime minister", "cabinet",
        "election commission", "isro", "drdo",
    ]
    if any(inst in text for inst in major_institutions):
        score += 1.5

    # Major policy/economic events
    policy_words = [
        "budget", "gdp", "inflation", "reform", "policy", "bill",
        "act", "amendment", "tax", "subsidy", "regulation",
    ]
    if any(w in text for w in policy_words):
        score += 1.0

    # Significance markers
    if any(w in text for w in ["historic", "landmark", "unprecedented", "major", "crisis"]):
        score += 0.5

    return min(score, 3.0)


def _score_market_relevance(item: IntelligenceItem, config: Config) -> float:
    """Score market relevance based on event impact."""
    text = f"{item.title} {item.summary or ''}".lower()
    score = 0.0

    # High priority market events
    market_events = config.markets_config.get("high_priority", [])
    hits = sum(1 for e in market_events if e.lower() in text)
    score += min(hits * 0.5, 1.5)

    # Central bank / policy events get boost
    cb_words = ["fed", "rbi", "ecb", "bank of japan", "interest rate",
                "rate cut", "rate hike", "monetary policy"]
    if any(w in text for w in cb_words):
        score += 1.0

    # Significance markers
    if any(w in text for w in [
        "crash", "surge", "plunge", "soar", "collapse", "record",
        "historic", "unprecedented", "worst", "best",
    ]):
        score += 0.5

    return min(score, 3.0)


def _score_technology_relevance(item: IntelligenceItem, config: Config) -> float:
    """Score technology announcement relevance."""
    text = f"{item.title} {item.summary or ''}".lower()
    score = 0.0

    # Major event types
    major_events = config.technology_config.get("major_events", [])
    hits = sum(1 for e in major_events if e.lower() in text)
    score += min(hits * 0.5, 1.5)

    # Tracked companies boost
    for company in config.tracked_companies:
        if company.lower() in text:
            score += 0.5
            break

    # Product/architecture launch words
    launch_words = [
        "launch", "unveil", "announce", "introduce", "release",
        "breakthrough", "revolutionize", "next-generation", "new architecture",
    ]
    if any(w in text for w in launch_words):
        score += 0.5

    # AI-specific tech announcements
    ai_words = ["ai model", "foundation model", "new llm", "ai chip",
                "ai accelerator", "neural", "machine learning"]
    if any(w in text for w in ai_words):
        score += 0.5

    return min(score, 3.0)
