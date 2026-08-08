"""Enrichment orchestrator — dispatches items to appropriate enrichment services."""

from __future__ import annotations

import logging

from src.config import Config
from src.enrichment.github_enrichment import GitHubClient
from src.enrichment.semantic_scholar import SemanticScholarClient
from src.models import Domain, IntelligenceItem

logger = logging.getLogger(__name__)


def enrich_items(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Enrich items with external metadata.

    Dispatches research items to Semantic Scholar and GitHub.
    Handles API failures gracefully.
    """
    config = Config.get()

    s2_client = None
    gh_client = None

    if config.semantic_scholar_enabled:
        s2_client = SemanticScholarClient(api_key=config.semantic_scholar_api_key)

    if config.github_enrichment_enabled:
        gh_client = GitHubClient(token=config.github_token)

    s2_matched = 0
    s2_total = 0
    gh_matched = 0
    gh_total = 0

    for item in items:
        # Semantic Scholar: only for research items with arXiv/DOI (max 15 requests per run)
        if s2_client and item.domain == Domain.AI_RESEARCH and s2_total < 15:
            if item.arxiv_id or item.doi:
                s2_total += 1
                try:
                    item = s2_client.enrich_item(item)
                    if item.semantic_scholar_id:
                        s2_matched += 1
                except Exception as e:
                    logger.warning(f"[ENRICH] S2 error for {item.title[:50]}: {e}")

        # GitHub: only for research items (max 15 requests per run)
        if gh_client and item.domain == Domain.AI_RESEARCH and gh_total < 15:
            if item.github_url or item.arxiv_id:
                gh_total += 1
                try:
                    item = gh_client.enrich_item(item)
                    if item.github_stars > 0:
                        gh_matched += 1
                except Exception as e:
                    logger.warning(f"[ENRICH] GH error for {item.title[:50]}: {e}")

    logger.info(
        f"[ENRICH] Semantic Scholar: {s2_matched}/{s2_total} matched | "
        f"GitHub: {gh_matched}/{gh_total} matched"
    )

    return items
