"""Text and data normalization for the intelligence pipeline."""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from src.models import IntelligenceItem

# Tracking params to strip
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "ncid", "ocid", "s", "smid",
}

# arXiv ID patterns
_ARXIV_PATTERN = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
_ARXIV_URL_PATTERN = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")

# DOI pattern
_DOI_PATTERN = re.compile(r"(10\.\d{4,9}/[^\s]+)")

# Common source prefixes to strip from titles
_TITLE_PREFIXES = [
    "BREAKING:", "BREAKING -", "EXCLUSIVE:", "UPDATE:", "UPDATE -",
    "WATCH:", "LIVE:", "JUST IN:",
]


def normalize_title(title: str) -> str:
    """Clean and normalize a title string."""
    # Decode HTML entities
    title = html.unescape(title)

    # Strip HTML tags
    title = re.sub(r"<[^>]+>", "", title)

    # Strip common prefixes
    for prefix in _TITLE_PREFIXES:
        if title.upper().startswith(prefix):
            title = title[len(prefix):].strip()

    # Normalize whitespace
    title = re.sub(r"\s+", " ", title).strip()

    return title


def normalize_url(url: str) -> str:
    """Canonicalize a URL by stripping tracking params and normalizing."""
    parsed = urlparse(url)

    # Strip tracking parameters
    params = parse_qs(parsed.query)
    cleaned = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
    clean_query = urlencode(cleaned, doseq=True)

    # Normalize
    normalized = urlunparse(parsed._replace(
        query=clean_query,
        fragment="",
    ))

    # Strip trailing slash for consistency
    return normalized.rstrip("/")


def extract_arxiv_id(item: IntelligenceItem) -> str | None:
    """Extract arXiv ID from URL or text content."""
    # Check URL first
    if item.url:
        match = _ARXIV_URL_PATTERN.search(item.url)
        if match:
            return match.group(1)

    # Check title and summary
    for text in [item.title, item.summary or ""]:
        match = _ARXIV_PATTERN.search(text)
        if match:
            return match.group(1)

    return None


def extract_doi(item: IntelligenceItem) -> str | None:
    """Extract DOI from content."""
    for text in [item.url, item.title, item.summary or ""]:
        match = _DOI_PATTERN.search(text)
        if match:
            return match.group(1).rstrip(".")
    return None


def title_for_comparison(title: str) -> str:
    """Produce a normalized title suitable for dedup comparison.

    Lowercases, strips punctuation, collapses whitespace.
    """
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_items(items: list[IntelligenceItem]) -> list[IntelligenceItem]:
    """Apply normalization to all items."""
    for item in items:
        item.title = normalize_title(item.title)
        item.url = normalize_url(item.url)

        # Extract academic identifiers
        if not item.arxiv_id:
            item.arxiv_id = extract_arxiv_id(item)
        if not item.doi:
            item.doi = extract_doi(item)

        # Normalize summary
        if item.summary:
            item.summary = html.unescape(item.summary)
            item.summary = re.sub(r"<[^>]+>", " ", item.summary)
            item.summary = re.sub(r"\s+", " ", item.summary).strip()

    return items
