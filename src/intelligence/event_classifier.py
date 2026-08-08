"""Event classifier — identifies event types and assigns categories."""

from __future__ import annotations

import re

from src.config import Config
from src.models import Domain, IntelligenceItem


def classify_event(item: IntelligenceItem) -> IntelligenceItem:
    """Classify an item's event type and assign categories from the taxonomy."""
    config = Config.get()
    text = f"{item.title} {item.summary or ''}".lower()
    categories: list[str] = list(item.categories)  # preserve existing

    if item.domain == Domain.AI_RESEARCH:
        categories.append("AI Research")
        categories.extend(_classify_ai_topics(text, config))

    elif item.domain == Domain.GEOPOLITICS:
        categories.append("Geopolitics")
        categories.extend(_classify_geopolitics(text, config))

    elif item.domain == Domain.INDIA:
        categories.append("India")
        categories.extend(_classify_india(text, config))

    elif item.domain == Domain.MARKETS:
        categories.extend(_classify_markets(text, config))

    elif item.domain == Domain.TECHNOLOGY:
        categories.append("Technology")
        categories.extend(_classify_technology(text, config))

    # Company detection across all domains
    for company in config.tracked_companies:
        if company.lower() in text:
            if "Technology" not in categories:
                categories.append("Technology")
            break

    # Deduplicate categories
    seen: set[str] = set()
    unique_cats: list[str] = []
    for c in categories:
        if c not in seen:
            seen.add(c)
            unique_cats.append(c)

    item.categories = unique_cats
    return item


def _classify_ai_topics(text: str, config: Config) -> list[str]:
    """Assign AI-specific categories."""
    cats: list[str] = []
    topic_map = {
        "LLM": ["llm", "large language model", "large language models"],
        "Agents": ["agent", "agents", "agentic"],
        "RAG": ["rag", "retrieval augmented", "retrieval-augmented"],
        "Multimodal": ["multimodal", "multi-modal", "vision-language", "vlm"],
        "Computer Vision": ["computer vision", "object detection", "image recognition"],
        "NLP": ["nlp", "natural language processing"],
        "Generative AI": ["generative ai", "generative model", "diffusion", "gan"],
        "AI Systems": ["mlsys", "ml systems", "inference", "training efficiency"],
    }
    for cat, keywords in topic_map.items():
        for kw in keywords:
            if kw in text:
                cats.append(cat)
                break
    if not cats:
        cats.append("Research")
    return cats


def _classify_geopolitics(text: str, config: Config) -> list[str]:
    """Assign geopolitics categories."""
    cats: list[str] = []
    if any(w in text for w in ["india", "delhi", "modi"]):
        cats.append("India")
    cats.append("World")

    if any(w in text for w in ["military", "defense", "missile", "army", "navy", "war"]):
        cats.append("Defense")
    if any(w in text for w in ["diplomat", "embassy", "ambassador", "summit", "talks"]):
        cats.append("Diplomacy")
    if any(w in text for w in ["trade", "tariff", "trade deal", "trade war", "sanction"]):
        cats.append("Trade")
    return cats


def _classify_india(text: str, config: Config) -> list[str]:
    """Assign India-specific categories."""
    cats: list[str] = []
    if any(w in text for w in ["rbi", "reserve bank", "sebi", "budget", "gdp", "inflation"]):
        cats.append("Economy")
    if any(w in text for w in ["supreme court", "parliament", "lok sabha", "rajya sabha"]):
        cats.append("India")
    if any(w in text for w in ["military", "defense", "isro", "drdo"]):
        cats.append("Defense")
    if any(w in text for w in ["election", "voting", "poll"]):
        cats.append("India")
    return cats if cats else ["India"]


def _classify_markets(text: str, config: Config) -> list[str]:
    """Assign market categories."""
    cats: list[str] = []
    indian_markers = ["nifty", "sensex", "rbi", "sebi", "rupee", "nse", "bse",
                       "fii", "dii", "india"]
    global_markers = ["fed", "ecb", "s&p", "nasdaq", "dow", "treasury",
                       "wall street", "federal reserve"]

    if any(m in text for m in indian_markers):
        cats.append("Indian Markets")
    if any(m in text for m in global_markers):
        cats.append("Global Markets")
    if not cats:
        cats.append("Global Markets")  # Default

    if any(w in text for w in ["gdp", "inflation", "employment", "jobs"]):
        cats.append("Economy")
    if any(w in text for w in ["fed", "rbi", "ecb", "bank of japan", "central bank",
                                 "interest rate", "rate cut", "rate hike"]):
        cats.append("Central Banks")
    if any(w in text for w in ["oil", "gold", "crude", "commodity"]):
        cats.append("Commodities")
    return cats


def _classify_technology(text: str, config: Config) -> list[str]:
    """Assign technology categories."""
    cats: list[str] = []
    if any(w in text for w in ["chip", "semiconductor", "gpu", "cpu", "processor",
                                 "silicon", "fab", "nm process", "tsmc"]):
        cats.append("Semiconductors")
    if any(w in text for w in ["cloud", "aws", "azure", "gcp"]):
        cats.append("Cloud")
    if any(w in text for w in ["hardware", "device", "laptop", "phone"]):
        cats.append("Hardware")
    if any(w in text for w in ["software", "os", "update", "release"]):
        cats.append("Software")
    if any(w in text for w in ["launch", "unveil", "announce", "introduce", "new product"]):
        cats.append("Product Launch")
    if any(w in text for w in ["acqui", "merger", "buy", "purchase"]):
        cats.append("Acquisition")
    if any(w in text for w in ["partner", "collaboration", "alliance"]):
        cats.append("Partnership")
    if any(w in text for w in ["ai", "machine learning", "model", "neural"]):
        cats.append("AI Research")
    return cats if cats else ["Technology"]


def classify_all(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Classify all items."""
    return [classify_event(item) for item in items]
