"""Noise filtering — aggressively remove low-value content."""

from __future__ import annotations

import logging
import re

from src.config import Config
from src.models import Domain, IntelligenceItem

logger = logging.getLogger(__name__)


def filter_items(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Apply domain-specific noise filters to remove low-value items.

    Returns filtered list. Items that fail filters are discarded.
    """
    config = Config.get()
    geo_noise = config.geopolitics_config.get("noise_keywords", [])
    market_noise = config.markets_config.get("noise_indicators", [])
    tech_noise = config.technology_config.get("noise_indicators", [])

    filtered: list[IntelligenceItem] = []
    removed = 0

    for item in items:
        text = f"{item.title} {item.summary or ''}".lower()

        # Domain-specific noise checks
        if item.domain == Domain.GEOPOLITICS or item.domain == Domain.INDIA:
            if _is_geopolitical_noise(text, geo_noise):
                removed += 1
                continue

        elif item.domain == Domain.MARKETS:
            if _is_market_noise(text, market_noise):
                removed += 1
                continue

        elif item.domain == Domain.TECHNOLOGY:
            if _is_tech_noise(text, tech_noise):
                removed += 1
                continue

        elif item.domain == Domain.AI_RESEARCH:
            if _is_research_noise(text):
                removed += 1
                continue

        # Universal noise check
        if _is_universal_noise(text):
            # Don't remove, but apply penalty
            item.noise_penalty = 1.0

        filtered.append(item)

    logger.info(f"[FILTER] {removed} items filtered as noise, {len(filtered)} remain")
    return filtered


def _is_geopolitical_noise(text: str, noise_keywords: list[str]) -> bool:
    """Check for geopolitical noise patterns."""
    for kw in noise_keywords:
        if kw.lower() in text:
            return True

    # Additional patterns
    noise_patterns = [
        r"\bopinion\b.*\bcolumn\b",
        r"\bletter to\b",
        r"\beditorial\b",
    ]
    for pattern in noise_patterns:
        if re.search(pattern, text):
            return True

    return False


def _is_market_noise(text: str, noise_keywords: list[str]) -> bool:
    """Check for market noise patterns."""
    for kw in noise_keywords:
        if kw.lower() in text:
            return True

    # Small price movement detection
    # "rises 0.5%", "falls 1.2%" etc — small moves are noise
    small_move = re.search(r"(?:rises?|falls?|up|down)\s+(\d+\.?\d*)\s*%", text)
    if small_move:
        pct = float(small_move.group(1))
        # Check if this is about an index (Nifty, Sensex, S&P etc)
        is_index = any(idx in text for idx in [
            "nifty", "sensex", "s&p", "nasdaq", "dow", "ftse", "dax"
        ])
        if is_index and pct < 2.0:
            return True
        elif not is_index and pct < 5.0:
            # Individual stock small moves
            # Only filter if no significant event context
            event_words = ["earnings", "acquisition", "merger", "layoff", "ceo",
                           "investigation", "recall", "bankruptcy", "ipo"]
            if not any(w in text for w in event_words):
                return True

    return False


def _is_tech_noise(text: str, noise_keywords: list[str]) -> bool:
    """Check for technology noise patterns."""
    for kw in noise_keywords:
        if kw.lower() in text:
            return True
    return False


def _is_research_noise(text: str) -> bool:
    """Check if a research item is low-priority routine work."""
    low_priority_only = [
        "survey of", "review of", "literature review",
    ]
    for pattern in low_priority_only:
        if pattern in text:
            # Only noise if no high-priority topic is present
            high_topics = [
                "llm", "large language", "foundation model", "agent",
                "reasoning", "multimodal", "transformer", "diffusion",
                "reinforcement learning", "alignment", "safety",
            ]
            if not any(t in text for t in high_topics):
                return True
    return False


def _is_universal_noise(text: str) -> bool:
    """Check for universal noise patterns (applies penalty, doesn't remove)."""
    patterns = [
        "you won't believe",
        "shocking",
        "epic fail",
        "internet reacts",
        "goes viral",
    ]
    return any(p in text for p in patterns)
