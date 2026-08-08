"""GitHub API client for repository metadata enrichment."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import requests

from src.config import CACHE_DIR
from src.models import IntelligenceItem

logger = logging.getLogger(__name__)

CACHE_FILE = CACHE_DIR / "github.json"
API_BASE = "https://api.github.com"
REQUEST_TIMEOUT = 10
RATE_LIMIT_DELAY = 1.0

# Pattern to extract GitHub repo from URLs
_GITHUB_REPO_PATTERN = re.compile(
    r"github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"
)


class GitHubClient:
    """Client for GitHub API with caching and rate limiting."""

    def __init__(self, token: str = "") -> None:
        self.token = token
        self._cache: dict[str, dict] = self._load_cache()
        self._last_request_time = 0.0

    def _load_cache(self) -> dict[str, dict]:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_cache(self) -> None:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except OSError as e:
            logger.warning(f"[GH] Failed to save cache: {e}")

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def get_repo_info(self, repo_path: str) -> dict | None:
        """Get repository metadata (stars, forks, etc.)."""
        if repo_path in self._cache:
            return self._cache[repo_path]

        self._rate_limit()

        try:
            url = f"{API_BASE}/repos/{repo_path}"
            resp = requests.get(
                url,
                headers=self._get_headers(),
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 403:
                logger.warning("[GH] Rate limited")
                return None

            if resp.status_code == 404:
                self._cache[repo_path] = {}
                return None

            resp.raise_for_status()
            data = resp.json()

            # Cache only what we need
            cached = {
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "watchers": data.get("watchers_count", 0),
                "created_at": data.get("created_at", ""),
                "pushed_at": data.get("pushed_at", ""),
                "description": data.get("description", ""),
            }
            self._cache[repo_path] = cached
            self._save_cache()
            return cached

        except requests.RequestException as e:
            logger.warning(f"[GH] API error for {repo_path}: {e}")
            return None

    def enrich_item(self, item: IntelligenceItem) -> IntelligenceItem:
        """Enrich an item with GitHub repository data."""
        # Try to find a GitHub URL in the item
        github_url = item.github_url
        if not github_url:
            # Search in content for GitHub URLs
            text = f"{item.url} {item.summary or ''}"
            match = _GITHUB_REPO_PATTERN.search(text)
            if match:
                github_url = match.group(1)

        if not github_url:
            return item

        # Clean the repo path
        repo_path = github_url.rstrip("/")
        # Remove .git suffix
        if repo_path.endswith(".git"):
            repo_path = repo_path[:-4]

        info = self.get_repo_info(repo_path)
        if not info or not info.get("stars"):
            return item

        item.github_url = f"https://github.com/{repo_path}"
        item.github_stars = max(item.github_stars, info.get("stars", 0))
        item.github_forks = max(item.github_forks, info.get("forks", 0))

        return item
