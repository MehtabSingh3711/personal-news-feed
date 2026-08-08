"""Hybrid story clustering — groups articles reporting the same event.

Combines:
  1. TF-IDF + cosine similarity on title/summary text
  2. Named entity overlap (countries, companies, people)
  3. Date proximity (same-day boost)
  4. Domain/event-type matching

Different articles about the same real-world event become one StoryCluster.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from src.models import Domain, IntelligenceItem, StoryCluster
from src.processing.normalization import title_for_comparison

logger = logging.getLogger(__name__)

# ── Clustering thresholds ────────────────────────────────────
TEXT_SIM_WEIGHT = 0.45
ENTITY_SIM_WEIGHT = 0.30
DATE_SIM_WEIGHT = 0.15
DOMAIN_SIM_WEIGHT = 0.10
CLUSTER_THRESHOLD = 0.50  # Minimum combined similarity to merge

# ── Named Entity Patterns ───────────────────────────────────
_COUNTRIES = [
    "india", "china", "pakistan", "us", "usa", "united states", "russia",
    "ukraine", "israel", "iran", "eu", "european union", "japan", "germany",
    "france", "uk", "united kingdom", "brazil", "turkey", "saudi arabia",
    "south korea", "north korea", "taiwan", "australia", "canada",
    "gaza", "palestine", "nato", "asean", "brics",
]

_COMPANIES = [
    "nvidia", "apple", "google", "microsoft", "samsung", "meta", "amazon",
    "openai", "anthropic", "amd", "intel", "qualcomm", "tesla", "deepmind",
    "hugging face", "huggingface", "alphabet", "facebook", "aws",
    "tsmc", "broadcom", "oracle", "ibm", "adobe", "salesforce",
]

_INSTITUTIONS = [
    "rbi", "sebi", "federal reserve", "fed", "ecb", "imf", "world bank",
    "supreme court", "parliament", "congress", "senate", "pentagon",
    "nasa", "who", "un", "united nations",
]

ALL_ENTITIES = _COUNTRIES + _COMPANIES + _INSTITUTIONS


def _extract_entities(text: str) -> set[str]:
    """Extract named entities from text using pattern matching."""
    text_lower = text.lower()
    found: set[str] = set()
    for entity in ALL_ENTITIES:
        # Use word boundary matching for short entities
        if len(entity) <= 3:
            if re.search(rf"\b{re.escape(entity)}\b", text_lower):
                found.add(entity)
        else:
            if entity in text_lower:
                found.add(entity)
    return found


def _text_for_clustering(item: IntelligenceItem) -> str:
    """Combine title and summary for TF-IDF vectorization."""
    parts = [item.title]
    if item.summary:
        parts.append(item.summary[:500])
    return " ".join(parts)


def _entity_similarity(entities_a: set[str], entities_b: set[str]) -> float:
    """Jaccard similarity of entity sets."""
    if not entities_a and not entities_b:
        return 0.0
    if not entities_a or not entities_b:
        return 0.0
    intersection = entities_a & entities_b
    union = entities_a | entities_b
    return len(intersection) / len(union)


def _date_similarity(item_a: IntelligenceItem, item_b: IntelligenceItem) -> float:
    """Score based on date proximity. Same day = 1.0, decays over days."""
    if not item_a.published_at or not item_b.published_at:
        return 0.5  # Unknown dates get neutral score
    delta = abs((item_a.published_at - item_b.published_at).total_seconds())
    hours = delta / 3600
    if hours <= 6:
        return 1.0
    elif hours <= 24:
        return 0.8
    elif hours <= 48:
        return 0.5
    elif hours <= 72:
        return 0.3
    return 0.1


def _domain_similarity(item_a: IntelligenceItem, item_b: IntelligenceItem) -> float:
    """Score 1.0 if same domain, 0.0 otherwise."""
    return 1.0 if item_a.domain == item_b.domain else 0.0


def cluster_stories(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Cluster items reporting the same event into StoryCluster groups.

    Buckets items by domain first, then uses vectorized TF-IDF + entity/date filtering
    to group items fast even with thousands of items.
    """
    if not items:
        return items

    # Group items by domain to avoid comparing cross-domain items
    domain_groups: dict[Domain, list[IntelligenceItem]] = {}
    for item in items:
        domain_groups.setdefault(item.domain, []).append(item)

    output: list[IntelligenceItem] = []
    merged_count = 0

    for domain, group_items in domain_groups.items():
        if len(group_items) == 1:
            output.append(group_items[0])
            continue

        n = len(group_items)
        texts = [_text_for_clustering(item) for item in group_items]
        entities = [_extract_entities(texts[i]) for i in range(n)]
        text_sims = _compute_tfidf_similarity(texts)

        cluster_assignments: list[int] = list(range(n))

        for i in range(n):
            for j in range(i + 1, n):
                text_sim = text_sims[i][j] if text_sims else 0.0
                entity_sim = _entity_similarity(entities[i], entities[j])

                # Quick pre-filter: skip expensive date calculation if text & entity similarity are both tiny
                if text_sim < 0.15 and entity_sim < 0.15:
                    continue

                date_sim = _date_similarity(group_items[i], group_items[j])
                domain_sim = 1.0  # Same domain bucket

                combined = (
                    TEXT_SIM_WEIGHT * text_sim
                    + ENTITY_SIM_WEIGHT * entity_sim
                    + DATE_SIM_WEIGHT * date_sim
                    + DOMAIN_SIM_WEIGHT * domain_sim
                )

                if combined >= CLUSTER_THRESHOLD:
                    root_i = _find_root(cluster_assignments, i)
                    root_j = _find_root(cluster_assignments, j)
                    if root_i != root_j:
                        cluster_assignments[root_j] = root_i

        for i in range(n):
            cluster_assignments[i] = _find_root(cluster_assignments, i)

        clusters: dict[int, list[int]] = {}
        for i, root in enumerate(cluster_assignments):
            clusters.setdefault(root, []).append(i)

        for root, member_indices in clusters.items():
            if len(member_indices) == 1:
                output.append(group_items[member_indices[0]])
                continue

            cluster_items = [group_items[i] for i in member_indices]
            best = max(cluster_items, key=lambda x: x.source_score)

            all_sources = set()
            for ci in cluster_items:
                all_sources.add(ci.source)
                all_sources.update(ci.cluster_sources)
            best.cluster_sources = list(all_sources - {best.source})
            best.cluster_id = f"cluster_{domain.value}_{root}"

            for ci in cluster_items:
                if ci is best:
                    continue
                best.hf_upvotes = max(best.hf_upvotes, ci.hf_upvotes)
                best.github_stars = max(best.github_stars, ci.github_stars)
                best.citation_count = max(best.citation_count, ci.citation_count)
                if ci.arxiv_id and not best.arxiv_id:
                    best.arxiv_id = ci.arxiv_id
                if ci.doi and not best.doi:
                    best.doi = ci.doi
                if ci.summary and (not best.summary or len(ci.summary) > len(best.summary)):
                    best.summary = ci.summary

            output.append(best)
            merged_count += len(member_indices) - 1

    logger.info(
        f"[CLUSTER] {merged_count} stories merged into clusters, "
        f"{len(output)} unique stories remain"
    )
    return output


def _find_root(assignments: list[int], i: int) -> int:
    """Union-find root with path compression."""
    while assignments[i] != i:
        assignments[i] = assignments[assignments[i]]
        i = assignments[i]
    return i


def _compute_tfidf_similarity(texts: list[str]) -> list[list[float]]:
    """Compute pairwise cosine similarity using TF-IDF.

    Returns an n×n matrix. Falls back to empty matrix if sklearn is unavailable.
    """
    n = len(texts)
    if n == 0:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        sim_matrix = cosine_similarity(tfidf_matrix)
        return sim_matrix.tolist()

    except ImportError:
        logger.warning("[CLUSTER] scikit-learn not available, using title similarity only")
        # Fallback: simple title similarity
        from difflib import SequenceMatcher
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                ratio = SequenceMatcher(
                    None,
                    title_for_comparison(texts[i]),
                    title_for_comparison(texts[j]),
                ).ratio()
                matrix[i][j] = ratio
                matrix[j][i] = ratio
            matrix[i][i] = 1.0
        return matrix
