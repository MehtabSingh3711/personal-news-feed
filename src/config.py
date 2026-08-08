"""Configuration loader for the Personal Intelligence Engine."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from src.models import Domain, SourceConfig

# Load .env if present
load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"


def _load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML config file from the config directory."""
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Config:
    """Central configuration for the intelligence engine."""

    _instance: Config | None = None

    def __init__(self) -> None:
        self._sources_raw = _load_yaml("sources.yaml")
        self._scoring_raw = _load_yaml("scoring.yaml")
        self._topics_raw = _load_yaml("topics.yaml")

    @classmethod
    def get(cls) -> Config:
        """Get or create the singleton config instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    # ── Sources ──────────────────────────────────────────────

    def get_sources(self, domain: str | None = None) -> list[SourceConfig]:
        """Get all enabled source configs, optionally filtered by domain."""
        sources: list[SourceConfig] = []
        raw = self._sources_raw.get("sources", {})
        for domain_key, source_list in raw.items():
            if domain is not None and domain_key != domain:
                continue
            for s in source_list:
                cfg = SourceConfig(**s)
                if cfg.enabled:
                    sources.append(cfg)
        return sources

    def get_domain_for_source(self, source_name: str) -> Domain:
        """Look up which domain a source belongs to."""
        raw = self._sources_raw.get("sources", {})
        for domain_key, source_list in raw.items():
            for s in source_list:
                if s["name"] == source_name:
                    try:
                        return Domain(domain_key)
                    except ValueError:
                        return Domain.GEOPOLITICS
        return Domain.GEOPOLITICS

    # ── Scoring ──────────────────────────────────────────────

    @property
    def thresholds(self) -> dict[str, float]:
        return self._scoring_raw.get("thresholds", {"must_read": 8.0, "worth_knowing": 6.0})

    @property
    def recency_config(self) -> dict[str, Any]:
        return self._scoring_raw.get("recency", {
            "half_life_hours": 48,
            "max_age_days": 7,
            "boost_hours": 6,
        })

    @property
    def llm_blend(self) -> dict[str, float]:
        return self._scoring_raw.get("llm_blend", {
            "deterministic_weight": 0.70,
            "llm_weight": 0.30,
            "top_k_candidates": 30,
        })

    @property
    def scoring_profiles(self) -> dict[str, dict[str, float]]:
        return self._scoring_raw.get("scoring_profiles", {})

    @property
    def noise_penalties(self) -> dict[str, float]:
        return self._scoring_raw.get("noise_penalties", {})

    @property
    def venue_bonuses(self) -> dict[str, float]:
        return self._scoring_raw.get("venue_bonuses", {})

    @property
    def cross_source_config(self) -> dict[str, float]:
        return self._scoring_raw.get("cross_source", {})

    @property
    def source_quality(self) -> dict[str, float]:
        return self._scoring_raw.get("source_quality", {})

    # ── Topics ───────────────────────────────────────────────

    @property
    def ai_topics(self) -> dict[str, list[dict]]:
        return self._topics_raw.get("ai_topics", {})

    @property
    def ai_venues(self) -> dict[str, list[str]]:
        return self._topics_raw.get("ai_venues", {})

    @property
    def geopolitics_config(self) -> dict[str, list[str]]:
        return self._topics_raw.get("geopolitics", {})

    @property
    def markets_config(self) -> dict[str, list[str]]:
        return self._topics_raw.get("markets", {})

    @property
    def technology_config(self) -> dict[str, list[str]]:
        return self._topics_raw.get("technology", {})

    @property
    def tracked_companies(self) -> list[str]:
        return self._topics_raw.get("tracked_companies", [])

    @property
    def categories(self) -> list[str]:
        return self._topics_raw.get("categories", [])

    # ── Environment ──────────────────────────────────────────

    @property
    def llm_enabled(self) -> bool:
        return os.getenv("LLM_ENABLED", "false").lower() == "true"

    @property
    def llm_provider(self) -> str:
        return os.getenv("LLM_PROVIDER", "gemini")

    @property
    def llm_model(self) -> str:
        return os.getenv("LLM_MODEL", "gemini-2.5-flash")

    @property
    def llm_api_key(self) -> str:
        return os.getenv("LLM_API_KEY", "")

    @property
    def semantic_scholar_enabled(self) -> bool:
        return os.getenv("SEMANTIC_SCHOLAR_ENABLED", "true").lower() == "true"

    @property
    def semantic_scholar_api_key(self) -> str:
        return os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

    @property
    def github_enrichment_enabled(self) -> bool:
        return os.getenv("GITHUB_ENRICHMENT_ENABLED", "true").lower() == "true"

    @property
    def github_token(self) -> str:
        return os.getenv("GITHUB_TOKEN", "")
