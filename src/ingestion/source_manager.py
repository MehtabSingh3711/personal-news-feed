"""Source manager — orchestrates ingestion from all configured sources."""

from __future__ import annotations

import logging

from src.config import Config
from src.ingestion.github_ingestion import fetch_github_intelligence
from src.ingestion.hf_papers import fetch_hf_papers
from src.ingestion.rss import fetch_feed
from src.models import Domain, IntelligenceItem

logger = logging.getLogger(__name__)


# Map config domain keys to Domain enum
DOMAIN_MAP: dict[str, Domain] = {
    "ai_research": Domain.AI_RESEARCH,
    "geopolitics": Domain.GEOPOLITICS,
    "india": Domain.INDIA,
    "markets": Domain.MARKETS,
    "technology": Domain.TECHNOLOGY,
    "github": Domain.GITHUB,
}


def ingest_all_sources() -> list[IntelligenceItem]:
    """Ingest items from every enabled source.

    Dispatches to the correct fetcher (RSS vs HF API vs GitHub API).
    Survives individual source failures.
    """
    config = Config.get()
    all_items: list[IntelligenceItem] = []
    stats: dict[str, int] = {}

    # 1. Fetch GitHub Intelligence
    try:
        gh_items = fetch_github_intelligence(token=config.github_token)
        all_items.extend(gh_items)
        stats["GitHub Intelligence"] = len(gh_items)
    except Exception as e:
        logger.error(f"[INGEST] GitHub Intelligence failed: {e}")
        stats["GitHub Intelligence"] = 0

    raw_sources = config._sources_raw.get("sources", {})

    for domain_key, source_list in raw_sources.items():
        domain = DOMAIN_MAP.get(domain_key, Domain.GEOPOLITICS)

        for source_cfg in source_list:
            if not source_cfg.get("enabled", True):
                continue

            name = source_cfg["name"]
            url = source_cfg["url"]

            try:
                if url.startswith("API:huggingface_papers"):
                    items = fetch_hf_papers()
                else:
                    from src.models import SourceConfig
                    sc = SourceConfig(**source_cfg)
                    items = fetch_feed(sc, domain)

                all_items.extend(items)
                stats[name] = len(items)

            except Exception as e:
                logger.error(f"[INGEST] Source {name} failed: {e}")
                stats[name] = 0

    # Log summary
    logger.info("[INGEST] === Ingestion Summary ===")
    total = 0
    for name, count in stats.items():
        logger.info(f"[INGEST]   {name}: {count}")
        total += count
    logger.info(f"[INGEST] Total: {total} items from {len(stats)} sources")

    return all_items
