"""Semantic Scholar API client with caching and rate limiting."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from src.config import CACHE_DIR
from src.models import IntelligenceItem

logger = logging.getLogger(__name__)

API_BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = "paperId,title,abstract,authors,venue,year,citationCount,referenceCount,externalIds,url"
RATE_LIMIT_DELAY = 1.0  # seconds between requests
REQUEST_TIMEOUT = 15
CACHE_FILE = CACHE_DIR / "semantic_scholar.json"


class SemanticScholarClient:
    """Client for the Semantic Scholar API with file-based caching."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key
        self._cache: dict[str, dict] = self._load_cache()
        self._last_request_time = 0.0

    def _load_cache(self) -> dict[str, dict]:
        """Load cached responses from disk."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_cache(self) -> None:
        """Persist cache to disk."""
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except OSError as e:
            logger.warning(f"[S2] Failed to save cache: {e}")

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def lookup_by_arxiv(self, arxiv_id: str) -> dict | None:
        """Look up a paper by arXiv ID."""
        cache_key = f"arxiv:{arxiv_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if getattr(self, "_rate_limited", False):
            return None

        self._rate_limit()

        try:
            url = f"{API_BASE}/paper/ARXIV:{arxiv_id}"
            resp = requests.get(
                url,
                params={"fields": FIELDS},
                headers=self._get_headers(),
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 429:
                logger.warning("[S2] Rate limited, skipping remaining S2 network calls")
                self._rate_limited = True
                return None

            if resp.status_code == 404:
                self._cache[cache_key] = {}
                return None

            resp.raise_for_status()
            data = resp.json()
            self._cache[cache_key] = data
            self._save_cache()
            return data

        except requests.RequestException as e:
            logger.warning(f"[S2] API error for arXiv {arxiv_id}: {e}")
            return None

    def lookup_by_doi(self, doi: str) -> dict | None:
        """Look up a paper by DOI."""
        cache_key = f"doi:{doi}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._rate_limit()

        try:
            url = f"{API_BASE}/paper/DOI:{doi}"
            resp = requests.get(
                url,
                params={"fields": FIELDS},
                headers=self._get_headers(),
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code in (404, 429):
                return None

            resp.raise_for_status()
            data = resp.json()
            self._cache[cache_key] = data
            self._save_cache()
            return data

        except requests.RequestException as e:
            logger.warning(f"[S2] API error for DOI {doi}: {e}")
            return None

    def enrich_item(self, item: IntelligenceItem) -> IntelligenceItem:
        """Enrich an intelligence item with Semantic Scholar data."""
        paper: dict | None = None

        # Try arXiv ID first, then DOI
        if item.arxiv_id:
            paper = self.lookup_by_arxiv(item.arxiv_id)
        if not paper and item.doi:
            paper = self.lookup_by_doi(item.doi)

        if not paper or not paper.get("paperId"):
            return item

        # Enrich the item
        item.semantic_scholar_id = paper.get("paperId")
        item.citation_count = max(
            item.citation_count, paper.get("citationCount", 0) or 0
        )

        if paper.get("venue") and not item.venue:
            item.venue = paper["venue"]

        if paper.get("abstract") and not item.summary:
            abstract = paper["abstract"]
            if len(abstract) > 1000:
                abstract = abstract[:997] + "..."
            item.summary = abstract

        if paper.get("authors") and not item.authors:
            item.authors = [
                a.get("name", "") for a in paper["authors"]
                if a.get("name")
            ]

        return item
