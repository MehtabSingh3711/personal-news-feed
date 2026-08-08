"""Deduplication — remove identical items appearing across sources."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from src.models import IntelligenceItem
from src.processing.normalization import normalize_url, title_for_comparison

logger = logging.getLogger(__name__)

TITLE_SIMILARITY_THRESHOLD = 0.85


def deduplicate(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Remove duplicate items using a multi-strategy cascade.

    Priority: DOI → arXiv ID → canonical URL → normalized title.
    When duplicates merge, keep the version from the highest-quality source.
    """
    # Index structures for fast lookup
    seen_doi: dict[str, int] = {}
    seen_arxiv: dict[str, int] = {}
    seen_url: dict[str, int] = {}
    seen_title_buckets: dict[str, list[tuple[str, int]]] = {}

    unique: list[IntelligenceItem] = []
    dup_count = 0

    for item in items:
        duplicate_of: int | None = None

        # 1. DOI match
        if item.doi and item.doi in seen_doi:
            duplicate_of = seen_doi[item.doi]

        # 2. arXiv ID match
        if duplicate_of is None and item.arxiv_id and item.arxiv_id in seen_arxiv:
            duplicate_of = seen_arxiv[item.arxiv_id]

        # 3. Canonical URL match
        if duplicate_of is None:
            canon_url = normalize_url(item.url)
            if canon_url in seen_url:
                duplicate_of = seen_url[canon_url]

        # 4. Normalized title similarity (bucketed by first token for O(1) candidate lookup)
        norm_title = title_for_comparison(item.title)
        first_word = norm_title.split()[0] if norm_title else ""

        if duplicate_of is None and first_word:
            candidates = seen_title_buckets.get(first_word, [])
            for existing_title, idx in candidates:
                ratio = SequenceMatcher(
                    None, norm_title, existing_title
                ).ratio()
                if ratio >= TITLE_SIMILARITY_THRESHOLD:
                    duplicate_of = idx
                    break

        if duplicate_of is not None:
            # Merge: keep higher-quality source version
            existing = unique[duplicate_of]
            if item.source_score > existing.source_score:
                # Replace with better source, but keep enrichment data
                item.hf_upvotes = max(item.hf_upvotes, existing.hf_upvotes)
                item.github_stars = max(item.github_stars, existing.github_stars)
                item.citation_count = max(item.citation_count, existing.citation_count)
                if existing.arxiv_id and not item.arxiv_id:
                    item.arxiv_id = existing.arxiv_id
                if existing.doi and not item.doi:
                    item.doi = existing.doi
                # Track that this item appeared in multiple sources
                if existing.source not in item.cluster_sources:
                    item.cluster_sources = list(
                        set(item.cluster_sources + existing.cluster_sources + [existing.source])
                    )
                unique[duplicate_of] = item
            else:
                # Keep existing, but note the extra source
                if item.source not in existing.cluster_sources:
                    existing.cluster_sources.append(item.source)
                existing.hf_upvotes = max(item.hf_upvotes, existing.hf_upvotes)
                existing.github_stars = max(item.github_stars, existing.github_stars)
                existing.citation_count = max(item.citation_count, existing.citation_count)
                if item.arxiv_id and not existing.arxiv_id:
                    existing.arxiv_id = item.arxiv_id
                if item.doi and not existing.doi:
                    existing.doi = item.doi

            dup_count += 1
        else:
            # New unique item
            idx = len(unique)
            unique.append(item)

            # Index it
            if item.doi:
                seen_doi[item.doi] = idx
            if item.arxiv_id:
                seen_arxiv[item.arxiv_id] = idx
            seen_url[normalize_url(item.url)] = idx
            if first_word:
                seen_title_buckets.setdefault(first_word, []).append((norm_title, idx))

    logger.info(f"[DEDUP] {dup_count} duplicates removed, {len(unique)} unique items")
    return unique
