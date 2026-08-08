"""RSS/Atom feed fetcher with robust error handling."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import feedparser
import requests

from src.models import Domain, IntelligenceItem, SourceConfig, SourceType

logger = logging.getLogger(__name__)

# Tracking parameter patterns to strip from URLs
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "ncid", "ocid",
}

REQUEST_TIMEOUT = 30
USER_AGENT = (
    "PersonalIntelligenceEngine/1.0 "
    "(+https://github.com/personal-intelligence)"
)


def _clean_url(url: str) -> str:
    """Strip tracking parameters from a URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    cleaned = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
    clean_query = urlencode(cleaned, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


def _generate_item_id(url: str, title: str) -> str:
    """Generate a stable, unique ID from URL and title."""
    key = f"{_clean_url(url)}|{title.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _parse_date(entry: dict[str, Any]) -> datetime | None:
    """Extract publication date from a feed entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                continue

    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass
    return None


def _extract_summary(entry: dict[str, Any]) -> str | None:
    """Extract a plain-text summary from a feed entry."""
    summary = entry.get("summary", "") or ""
    # Strip HTML tags
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    if len(summary) > 1000:
        summary = summary[:997] + "..."
    return summary if summary else None


def fetch_feed(source: SourceConfig, domain: Domain) -> list[IntelligenceItem]:
    """Fetch and parse a single RSS/Atom feed.

    Returns a list of IntelligenceItems. Never raises — returns empty
    list on failure.
    """
    items: list[IntelligenceItem] = []

    try:
        logger.info(f"[INGEST] Fetching {source.name}: {source.url}")

        # feedparser can fetch URLs directly, but we use requests for
        # better timeout / user-agent control.
        resp = requests.get(
            source.url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        if feed.bozo and not feed.entries:
            logger.warning(
                f"[INGEST] Malformed feed from {source.name}: {feed.bozo_exception}"
            )
            return items

        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()

            if not title or not link:
                continue

            link = _clean_url(link)
            item_id = _generate_item_id(link, title)
            pub_date = _parse_date(entry)

            item = IntelligenceItem(
                id=item_id,
                title=title,
                url=link,
                summary=_extract_summary(entry),
                published_at=pub_date,
                source=source.name,
                source_type=source.type,
                domain=domain,
                source_score=source.quality_score,
                categories=_extract_categories(entry),
            )

            items.append(item)

        logger.info(f"[INGEST] {source.name}: {len(items)} items")

    except requests.RequestException as e:
        logger.error(f"[INGEST] Failed to fetch {source.name}: {e}")
    except Exception as e:
        logger.error(f"[INGEST] Unexpected error for {source.name}: {e}")

    return items


def _extract_categories(entry: dict[str, Any]) -> list[str]:
    """Extract category tags from a feed entry."""
    cats: list[str] = []
    for tag in entry.get("tags", []):
        term = tag.get("term", "").strip()
        if term:
            cats.append(term)
    return cats
