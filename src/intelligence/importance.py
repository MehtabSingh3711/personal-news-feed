"""Domain-specific importance scoring.

Each domain has its own scoring profile that maps component scores
to a final 0–10 importance score:

- AI Research: novelty, research significance, academic/community impact
- Geopolitics: strategic/policy/international significance
- Markets: market/economic/policy impact
- Technology: technical/product/industry significance

All final scores are normalized to 0–10.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from src.config import Config
from src.intelligence.relevance import score_relevance
from src.models import Domain, IntelligenceItem, Classification


def compute_importance(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Compute the deterministic importance score for all items.

    Each item gets component scores and a final 0–10 deterministic score.
    """
    config = Config.get()

    for item in items:
        # 1. Relevance score (0-3)
        item.relevance_score = score_relevance(item)

        # 2. Domain-specific importance (0-3)
        item.importance_score = _domain_importance(item, config)

        # 3. Community / market signal (0-1)
        item.community_score = _community_score(item)

        # 4. Academic impact (0-1)
        item.academic_score = _academic_score(item, config)

        # 5. Source quality (0-1)
        item.source_score = _source_quality_score(item, config)

        # 6. Recency (0-1)
        item.recency_score = _recency_score(item, config)

        # 7. Cross-source confirmation bonus
        cross_bonus = _cross_source_bonus(item, config)

        # 8. Noise penalty
        noise = item.noise_penalty

        # Compose final deterministic score
        raw = (
            item.relevance_score
            + item.importance_score
            + item.community_score
            + item.academic_score
            + item.source_score
            + item.recency_score
            + cross_bonus
            - noise
        )

        # Clamp to 0-10
        item.deterministic_score = max(0.0, min(10.0, raw))
        item.final_score = item.deterministic_score  # May be blended later with LLM

    return items


def _domain_importance(item: IntelligenceItem, config: Config) -> float:
    """Compute domain-specific importance (0-3)."""
    text = f"{item.title} {item.summary or ''}".lower()

    if item.domain == Domain.AI_RESEARCH:
        return _ai_importance(item, text, config)
    elif item.domain == Domain.GEOPOLITICS:
        return _geopolitics_importance(text, config)
    elif item.domain == Domain.INDIA:
        return _india_importance(text, config)
    elif item.domain == Domain.MARKETS:
        return _market_importance(text, config)
    elif item.domain == Domain.TECHNOLOGY:
        return _tech_importance(text, config)

    return 1.0


def _ai_importance(item: IntelligenceItem, text: str, config: Config) -> float:
    """AI research importance: novelty + research significance."""
    score = 0.0

    # Novelty indicators
    novelty_words = [
        "novel", "new", "first", "state-of-the-art", "sota", "surpass",
        "outperform", "breakthrough", "propose", "introduce",
        "achieve", "advance", "beyond",
    ]
    novelty_hits = sum(1 for w in novelty_words if w in text)
    score += min(novelty_hits * 0.3, 1.0)

    # Methodology advancement vs application
    methodology_words = [
        "architecture", "framework", "algorithm", "method", "technique",
        "approach", "mechanism", "paradigm", "formulation",
    ]
    if any(w in text for w in methodology_words):
        score += 0.5

    # Scale / ambition indicators
    scale_words = [
        "billion", "trillion", "large-scale", "massive", "scalab",
        "foundation", "general", "universal", "unified",
    ]
    if any(w in text for w in scale_words):
        score += 0.5

    # Lab/origin prestige
    prestige_labs = [
        "google", "deepmind", "openai", "anthropic", "meta", "microsoft",
        "nvidia", "apple", "stanford", "mit", "berkeley", "carnegie mellon",
    ]
    all_text = f"{text} {' '.join(item.authors).lower()}"
    if any(lab in all_text for lab in prestige_labs):
        score += 0.5

    # Application-only penalty (no methodology contribution)
    app_only_words = [
        "we apply", "applied to", "case study", "using existing",
        "applied machine learning", "predict", "classification of",
    ]
    method_words = [
        "propose", "novel", "new method", "architecture", "introduce",
    ]
    if any(w in text for w in app_only_words) and not any(w in text for w in method_words):
        score -= 0.5

    return max(0.0, min(3.0, score))


def _geopolitics_importance(text: str, config: Config) -> float:
    """Geopolitical importance: strategic/policy/international significance."""
    score = 0.0

    # Material change indicators
    change_words = [
        "breakthrough", "historic", "unprecedented", "landmark",
        "crisis", "escalat", "war", "conflict", "invasion",
        "treaty", "agreement", "deal", "sanction",
        "nuclear", "military operation",
    ]
    hits = sum(1 for w in change_words if w in text)
    score += min(hits * 0.5, 1.5)

    # Number of countries/regions mentioned
    countries_mentioned = sum(1 for region in
        config.geopolitics_config.get("high_priority_regions", [])
        if region.lower() in text
    )
    score += min(countries_mentioned * 0.3, 0.9)

    # Leadership / high-level actors
    leaders = ["president", "prime minister", "chancellor", "king",
               "secretary general", "foreign minister", "defense minister"]
    if any(w in text for w in leaders):
        score += 0.3

    # Scope: global vs local
    global_words = ["global", "international", "worldwide", "multilateral"]
    if any(w in text for w in global_words):
        score += 0.3

    return min(3.0, score)


def _india_importance(text: str, config: Config) -> float:
    """Indian news importance: national significance."""
    score = 0.0

    # Top institutional events
    if any(w in text for w in ["supreme court", "rbi", "sebi", "budget",
                                 "parliament", "lok sabha"]):
        score += 1.0

    # Major policy events
    if any(w in text for w in ["reform", "policy change", "new law",
                                 "regulation", "amendment"]):
        score += 0.8

    # Impact scale
    if any(w in text for w in ["national", "across india", "crore", "billion",
                                 "million", "economy"]):
        score += 0.5

    # Significance markers
    if any(w in text for w in ["historic", "landmark", "unprecedented",
                                 "major", "crisis", "emergency"]):
        score += 0.7

    return min(3.0, score)


def _market_importance(text: str, config: Config) -> float:
    """Market importance: economic/policy/market impact."""
    score = 0.0

    # Central bank events (highest impact)
    if any(w in text for w in ["rate cut", "rate hike", "interest rate",
                                 "monetary policy", "quantitative"]):
        score += 1.5

    # Major economic data
    if any(w in text for w in ["gdp", "inflation", "cpi", "employment",
                                 "payroll", "nonfarm"]):
        score += 1.0

    # Large market movements
    big_move = re.search(r"(\d+\.?\d*)\s*%", text)
    if big_move:
        pct = float(big_move.group(1))
        if pct >= 5.0:
            score += 1.0
        elif pct >= 3.0:
            score += 0.5

    # M&A / structural events
    if any(w in text for w in ["merger", "acquisition", "ipo", "bankruptcy",
                                 "default", "restructur"]):
        score += 0.8

    # Budget / fiscal events
    if any(w in text for w in ["budget", "fiscal", "deficit", "surplus",
                                 "stimulus", "bailout"]):
        score += 0.7

    return min(3.0, score)


def _tech_importance(text: str, config: Config) -> float:
    """Technology importance: technical/product/industry significance."""
    score = 0.0

    # Product launches
    if any(w in text for w in ["launch", "unveil", "introduce", "announce",
                                 "release", "debut"]):
        score += 0.8

    # Hardware / chip events (very significant)
    if any(w in text for w in ["new chip", "new gpu", "new cpu",
                                 "new processor", "architecture",
                                 "fabrication", "nm process"]):
        score += 1.0

    # AI model releases
    if any(w in text for w in ["new model", "foundation model", "new llm",
                                 "gpt", "gemini", "claude", "llama"]):
        score += 1.0

    # Strategic / industry impact
    if any(w in text for w in ["acquisition", "merger", "billion",
                                 "partnership", "strategic"]):
        score += 0.7

    # Industry shift indicators
    if any(w in text for w in ["disrupt", "revolutionize", "transform",
                                 "game-changing", "industry-first"]):
        score += 0.5

    return min(3.0, score)


def _community_score(item: IntelligenceItem) -> float:
    """Community/market signal score (0-1) using log scaling."""
    if item.domain != Domain.AI_RESEARCH:
        return 0.0

    score = 0.0

    # HuggingFace upvotes (log scaled)
    if item.hf_upvotes > 0:
        # ~50 upvotes → ~0.5, ~200 upvotes → ~0.7, ~1000 → ~0.9
        score = max(score, min(1.0, math.log1p(item.hf_upvotes) / 8.0))

    # GitHub stars (log scaled)
    if item.github_stars > 0:
        score = max(score, min(1.0, math.log1p(item.github_stars) / 10.0))

    return score


def _academic_score(item: IntelligenceItem, config: Config) -> float:
    """Academic impact score (0-1): citations + venue quality."""
    if item.domain != Domain.AI_RESEARCH:
        return 0.0

    score = 0.0

    # Citation count (log scaled, for recent papers even a few is notable)
    if item.citation_count > 0:
        score += min(0.5, math.log1p(item.citation_count) / 8.0)

    # Venue quality bonus
    venue_bonuses = config.venue_bonuses
    if item.venue:
        venue_lower = item.venue.lower()
        venues = config.ai_venues

        for v in venues.get("tier_1", []):
            if v in venue_lower:
                score += venue_bonuses.get("tier_1", 0.8)
                break
        else:
            for v in venues.get("tier_2", []):
                if v in venue_lower:
                    score += venue_bonuses.get("tier_2", 0.5)
                    break
            else:
                for v in venues.get("tier_3", []):
                    if v in venue_lower:
                        score += venue_bonuses.get("tier_3", 0.3)
                        break
                else:
                    for v in venues.get("nature", []):
                        if v in venue_lower:
                            score += venue_bonuses.get("nature", 0.7)
                            break

    return min(1.0, score)


def _source_quality_score(item: IntelligenceItem, config: Config) -> float:
    """Source quality score (0-1) from config."""
    # Already set during ingestion, but normalize to 0-1
    return min(1.0, max(0.0, item.source_score))


def _recency_score(item: IntelligenceItem, config: Config) -> float:
    """Recency score (0-1) with exponential decay."""
    if not item.published_at:
        return 0.5  # Unknown date gets middle score

    recency_config = config.recency_config
    half_life_hours = recency_config.get("half_life_hours", 48)
    boost_hours = recency_config.get("boost_hours", 6)

    now = datetime.now(timezone.utc)
    age_hours = max(0, (now - item.published_at).total_seconds() / 3600)

    if age_hours <= boost_hours:
        return 1.0

    # Exponential decay
    decay = math.exp(-0.693 * (age_hours - boost_hours) / half_life_hours)
    return max(0.1, decay)


def _cross_source_bonus(item: IntelligenceItem, config: Config) -> float:
    """Bonus for cross-source confirmation."""
    cs_config = config.cross_source_config
    num_sources = len(item.cluster_sources) + 1  # +1 for primary source

    if num_sources >= 3:
        return cs_config.get("three_plus", 0.6)
    elif num_sources >= 2:
        return cs_config.get("two_sources", 0.3)
    return 0.0


def classify_items(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Apply final classification (MUST READ / WORTH KNOWING / DISCARDED)."""
    config = Config.get()
    must_read_threshold = config.thresholds.get("must_read", 8.0)
    worth_knowing_threshold = config.thresholds.get("worth_knowing", 6.0)

    for item in items:
        if item.final_score >= must_read_threshold:
            item.classification = Classification.MUST_READ
        elif item.final_score >= worth_knowing_threshold:
            item.classification = Classification.WORTH_KNOWING
        else:
            item.classification = Classification.DISCARDED

    return items
