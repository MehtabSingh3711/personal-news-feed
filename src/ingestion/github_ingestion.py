"""GitHub Intelligence Ingestor — fetches high-value AI/ML/LLM repositories via GitHub API."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

from src.models import Domain, IntelligenceItem, SourceType

logger = logging.getLogger(__name__)

SEARCH_API = "https://api.github.com/search/repositories"
REQUEST_TIMEOUT = 15

# Noise filters for generic tutorials, awesome lists, interview prep
NOISE_PATTERNS = [
    r"\bawesome-", r"\btutorial\b", r"\binterview\b", r"\broadmap\b",
    r"\bleetcode\b", r"\bcheatsheet\b", r"\bcurated list\b", r"\bcourse\b",
    r"\bcollection of\b", r"\bfree-certifications\b",
]

# Query categories to search
QUERY_TOPICS = [
    "topic:llm sort:updated",
    "topic:agents sort:updated",
    "topic:rag sort:updated",
    "topic:multimodal sort:updated",
    "topic:ai-infrastructure sort:updated",
    "topic:deep-learning sort:stars",
]


def fetch_github_intelligence(token: str = "", limit: int = 30) -> list[IntelligenceItem]:
    """Fetch high-value AI/ML repositories using the GitHub Search API.

    Filters out forks, tutorials, awesome lists, and abandoned projects.
    Extracts associated research papers (arXiv ID) if available.
    """
    items: list[IntelligenceItem] = []
    seen_repos: set[str] = set()

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    logger.info("[INGEST] Fetching GitHub Intelligence repositories")

    # Search past 30 days pushed repos
    date_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    queries = [
        f"topic:llm pushed:>{date_cutoff} stars:>50",
        f"topic:agents pushed:>{date_cutoff} stars:>50",
        f"topic:rag pushed:>{date_cutoff} stars:>30",
        f"topic:multimodal pushed:>{date_cutoff} stars:>30",
        f"topic:ai-infrastructure pushed:>{date_cutoff} stars:>30",
    ]

    for q in queries:
        if len(items) >= limit:
            break

        try:
            resp = requests.get(
                SEARCH_API,
                params={"q": f"{q} fork:false archived:false", "sort": "stars", "order": "desc", "per_page": 15},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code in (403, 429):
                logger.warning("[GH] Rate limited on search, proceeding with collected items")
                break

            resp.raise_for_status()
            data = resp.json()
            repos = data.get("items", [])

            for repo in repos:
                full_name = repo.get("full_name", "")
                if not full_name or full_name in seen_repos:
                    continue

                description = (repo.get("description") or "").strip()

                # Filter out generic tutorials, awesome lists, etc.
                if _is_github_noise(full_name, description):
                    continue

                seen_repos.add(full_name)

                stars = repo.get("stargazers_count", 0)
                forks = repo.get("forks_count", 0)
                topics = repo.get("topics", [])
                homepage = repo.get("homepage") or ""

                # Parse publication / arXiv link from description or homepage
                arxiv_id = _extract_arxiv(description + " " + homepage)
                paper_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None

                # Compute recency / updated date
                pushed_at_str = repo.get("pushed_at") or repo.get("updated_at")
                pub_date = None
                if pushed_at_str:
                    try:
                        pub_date = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                # Derive star growth indicator
                growth_text = f"{stars:,} ★"
                if stars > 1000:
                    growth_text = f"{stars/1000:.1f}k ★ · Active development"

                # Assign categories based on topics/description
                categories = _assign_github_categories(full_name, description, topics)

                item_id = hashlib.sha256(f"github|{full_name}".encode("utf-8")).hexdigest()[:16]

                title = f"{repo.get('name', full_name)}: {description}" if description else full_name
                if len(title) > 100:
                    title = title[:97] + "..."

                item = IntelligenceItem(
                    id=item_id,
                    title=title,
                    url=repo.get("html_url", f"https://github.com/{full_name}"),
                    github_url=repo.get("html_url", f"https://github.com/{full_name}"),
                    summary=description or f"Open-source repository {full_name}",
                    published_at=pub_date,
                    source="GitHub Intelligence",
                    source_type=SourceType.GITHUB,
                    domain=Domain.GITHUB,
                    categories=categories,
                    github_stars=stars,
                    github_forks=forks,
                    github_growth=growth_text,
                    arxiv_id=arxiv_id,
                    paper_url=paper_url,
                    source_score=0.95,
                )

                items.append(item)

        except requests.RequestException as e:
            logger.warning(f"[GH] Search failed for query '{q}': {e}")

    logger.info(f"[INGEST] GitHub Intelligence: {len(items)} repositories collected")
    return items


def _is_github_noise(full_name: str, description: str) -> bool:
    """Filter out noise repositories (tutorials, awesome lists, interview preps)."""
    text = f"{full_name} {description}".lower()
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def _extract_arxiv(text: str) -> str | None:
    """Extract arXiv ID from text string if present."""
    match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match_id = re.search(r"\b(\d{4}\.\d{4,5})\b", text)
    if match_id:
        return match_id.group(1)
    return None


def _assign_github_categories(name: str, desc: str, topics: list[str]) -> list[str]:
    """Assign categories to GitHub repo."""
    cats = ["GitHub"]
    text = f"{name} {desc} {' '.join(topics)}".lower()

    if any(k in text for k in ["llm", "large language", "prompt"]):
        cats.append("LLM")
    if any(k in text for k in ["agent", "agents", "agentic"]):
        cats.append("Agents")
    if any(k in text for k in ["rag", "retrieval", "vector"]):
        cats.append("RAG")
    if any(k in text for k in ["multimodal", "vision", "audio"]):
        cats.append("Multimodal")
    if any(k in text for k in ["infrastructure", "training", "inference", "quantization", "vllm"]):
        cats.append("Semiconductors")

    return cats
