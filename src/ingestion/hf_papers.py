"""HuggingFace Daily Papers API client."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import requests

from src.models import Domain, IntelligenceItem, SourceType

logger = logging.getLogger(__name__)

HF_API_URL = "https://huggingface.co/api/daily_papers"
REQUEST_TIMEOUT = 30


def fetch_hf_papers(limit: int = 50) -> list[IntelligenceItem]:
    """Fetch trending/daily papers from the HuggingFace API.

    Returns structured IntelligenceItems with upvotes, arXiv IDs, etc.
    Never raises — returns empty list on failure.
    """
    items: list[IntelligenceItem] = []

    try:
        logger.info("[INGEST] Fetching HuggingFace Daily Papers API")

        resp = requests.get(
            HF_API_URL,
            params={"limit": limit},
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        papers = resp.json()

        if not isinstance(papers, list):
            logger.warning("[INGEST] HF API returned unexpected format")
            return items

        for paper_data in papers:
            paper = paper_data.get("paper", paper_data)
            title = (paper.get("title") or "").strip()
            paper_id = paper.get("id", "")

            if not title:
                continue

            # Build arXiv URL from paper ID
            arxiv_id = paper_id
            url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""

            if not url:
                continue

            item_id = hashlib.sha256(
                f"hf_paper|{arxiv_id}".encode("utf-8")
            ).hexdigest()[:16]

            # Parse publication date
            pub_date = None
            date_str = paper_data.get("publishedAt") or paper.get("publishedAt")
            if date_str:
                try:
                    pub_date = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            # Extract authors
            authors = []
            for author in paper.get("authors", []):
                name = author if isinstance(author, str) else author.get("name", "")
                if name:
                    authors.append(name)

            summary = (paper.get("summary") or paper.get("abstract") or "").strip()
            if len(summary) > 1000:
                summary = summary[:997] + "..."

            upvotes = paper_data.get("paper", {}).get("upvotes", 0)
            if isinstance(paper_data.get("upvotes"), int):
                upvotes = paper_data["upvotes"]

            item = IntelligenceItem(
                id=item_id,
                title=title,
                url=url,
                summary=summary or None,
                published_at=pub_date,
                source="HuggingFace Daily Papers",
                source_type=SourceType.RESEARCH,
                domain=Domain.AI_RESEARCH,
                arxiv_id=arxiv_id,
                authors=authors,
                hf_upvotes=upvotes,
                source_score=0.95,
            )
            items.append(item)

        logger.info(f"[INGEST] HuggingFace Daily Papers: {len(items)} items")

    except requests.RequestException as e:
        logger.error(f"[INGEST] HuggingFace API failed: {e}")
    except Exception as e:
        logger.error(f"[INGEST] Unexpected error in HF papers: {e}")

    return items
