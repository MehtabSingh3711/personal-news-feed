"""Main pipeline for the Personal Intelligence Engine.

Executes the full pipeline:
  1. Load configuration
  2. Load state
  3. Ingest all sources
  4. Normalize
  5. Deduplicate
  6. Cluster stories
  7. Filter noise
  8. Enrich (Semantic Scholar, GitHub)
  9. Classify events
  10. Score (relevance + importance)
  11. Optional LLM second pass
  12. Classify (MUST READ / WORTH KNOWING / discard)
  13. Filter already-published items
  14. Generate feed.xml
  15. Save state
  16. Log summary
"""

from __future__ import annotations

import logging
import sys

from src.config import Config
from src.enrichment.metadata import enrich_items
from src.ingestion.source_manager import ingest_all_sources
from src.intelligence.event_classifier import classify_all
from src.intelligence.importance import classify_items, compute_importance
from src.intelligence.llm_judge import llm_evaluate
from src.models import Classification
from src.output.rss import generate_feed
from src.processing.clustering import cluster_stories
from src.processing.deduplication import deduplicate
from src.processing.filtering import filter_items
from src.processing.normalization import normalize_items
from src.state.state_manager import StateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    """Execute the full intelligence pipeline."""
    logger.info("=" * 60)
    logger.info("PERSONAL INTELLIGENCE ENGINE — Starting pipeline")
    logger.info("=" * 60)

    # 1. Load configuration
    config = Config.get()
    logger.info("[CONFIG] Configuration loaded")

    # 2. Load state
    state = StateManager()

    # 3. Ingest all sources
    logger.info("\n" + "=" * 40)
    items = ingest_all_sources()

    if not items:
        logger.warning("[PIPELINE] No items ingested, exiting")
        return

    # 4. Normalize
    logger.info("\n" + "=" * 40)
    items = normalize_items(items)
    logger.info(f"[NORMALIZE] {len(items)} items normalized")

    # 5. Deduplicate
    logger.info("\n" + "=" * 40)
    items = deduplicate(items)

    # 6. Cluster stories
    logger.info("\n" + "=" * 40)
    items = cluster_stories(items)

    # 7. Filter noise
    logger.info("\n" + "=" * 40)
    items = filter_items(items)

    # 8. Enrich (Semantic Scholar, GitHub)
    logger.info("\n" + "=" * 40)
    items = enrich_items(items)

    # 9. Classify event types and assign categories
    logger.info("\n" + "=" * 40)
    items = classify_all(items)
    logger.info(f"[CLASSIFY] {len(items)} items classified")

    # 10. Score (relevance + importance)
    logger.info("\n" + "=" * 40)
    items = compute_importance(items)
    logger.info("[SCORE] Importance scores computed")

    # 11. Optional LLM second pass
    logger.info("\n" + "=" * 40)
    items = llm_evaluate(items)

    # 12. Classify (MUST READ / WORTH KNOWING / discard)
    items = classify_items(items)

    # Count classifications
    must_read = [i for i in items if i.classification == Classification.MUST_READ]
    worth_knowing = [i for i in items if i.classification == Classification.WORTH_KNOWING]
    discarded = [i for i in items if i.classification == Classification.DISCARDED]

    logger.info(
        f"[SCORE] {len(must_read)} MUST READ | "
        f"{len(worth_knowing)} WORTH KNOWING | "
        f"{len(discarded)} discarded"
    )

    # 13. Collect all publishable items for feed.xml
    publishable = [
        i for i in items
        if i.classification in (Classification.MUST_READ, Classification.WORTH_KNOWING)
    ]

    # Sort publishable by final_score descending
    publishable.sort(key=lambda x: x.final_score, reverse=True)

    # 14. Generate feed.xml (always includes active top items so RSS readers can parse it)
    logger.info("\n" + "=" * 40)
    feed_path = generate_feed(publishable)

    # 15. Record state and save
    for item in publishable:
        state.record(item)
    state.prune()
    state.save()

    # 16. Summary
    logger.info("\n" + "=" * 60)
    logger.info("PERSONAL INTELLIGENCE ENGINE — Pipeline complete")
    logger.info(f"  Published: {len(publishable)} items")
    logger.info(f"  Feed: {feed_path}")
    logger.info(f"  State entries: {state.count}")
    logger.info("=" * 60)

    # Print top items
    if publishable:
        logger.info("\nTOP ITEMS:")
        for item in sorted(publishable, key=lambda x: x.final_score, reverse=True)[:10]:
            label = "[MUST READ]" if item.classification == Classification.MUST_READ else "[WORTH KNOWING]"
            logger.info(
                f"  {label} [{item.final_score:.1f}] {item.title[:80]}"
                f"  ({', '.join(item.categories[:3])})"
            )


if __name__ == "__main__":
    run_pipeline()
