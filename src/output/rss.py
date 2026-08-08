"""RSS 2.0 feed generator with multi-category feed support."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from src.config import PROJECT_ROOT
from src.models import Classification, Domain, IntelligenceItem
from src.output.formatter import format_description, format_title

logger = logging.getLogger(__name__)

FEED_FILE = PROJECT_ROOT / "feed.xml"
FEED_TITLE = "Personal Intelligence"
FEED_DESCRIPTION = (
    "High-signal intelligence briefing: AI research, geopolitics, "
    "financial markets, and major technology announcements."
)
FEED_LINK = "https://mehtabsingh3711.github.io/personal-news-feed"


def generate_feed(
    items: list[IntelligenceItem],
    output_path: Path | None = None,
    feed_title: str = FEED_TITLE,
    feed_filename: str = "feed.xml",
) -> Path:
    """Generate a valid RSS 2.0 feed file from scored and classified items."""
    path = output_path or (PROJECT_ROOT / feed_filename)

    # Filter to publishable items only
    publishable = [
        item for item in items
        if item.classification in (Classification.MUST_READ, Classification.WORTH_KNOWING)
    ]

    # Sort by score descending
    publishable.sort(key=lambda x: x.final_score, reverse=True)

    logger.info(f"[RSS] Generating {feed_filename} with {len(publishable)} items")

    # Build RSS XML
    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = feed_title
    SubElement(channel, "description").text = FEED_DESCRIPTION
    SubElement(channel, "link").text = FEED_LINK
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "lastBuildDate").text = _rfc822_now()
    SubElement(channel, "generator").text = "PersonalIntelligenceEngine/1.0"

    # Add self-referencing atom link
    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", f"{FEED_LINK}/{feed_filename}")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for item in publishable:
        _add_item(channel, item)

    # Serialize to pretty-printed XML
    xml_bytes = tostring(rss, encoding="unicode")
    xml_str = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding=None)

    lines = xml_str.split("\n")
    output = "\n".join(lines)

    # Write to file
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(output)

    # Validate
    _validate_feed(path)

    logger.info(f"[RSS] Written to {path}")
    return path


def generate_all_feeds(items: list[IntelligenceItem]) -> dict[str, Path]:
    """Generate master feed.xml and category-specific feeds."""
    result: dict[str, Path] = {}

    # Master feed
    result["master"] = generate_feed(items, feed_filename="feed.xml")

    # AI feed
    ai_items = [
        i for i in items
        if i.domain == Domain.AI_RESEARCH or any(c in i.categories for c in ["AI Research", "LLM", "Agents", "RAG", "Multimodal"])
    ]
    result["ai"] = generate_feed(ai_items, feed_title="Personal Intelligence — AI Research", feed_filename="ai.xml")

    # Geopolitics feed
    geo_items = [
        i for i in items
        if i.domain in (Domain.GEOPOLITICS, Domain.INDIA) or "Geopolitics" in i.categories or "India" in i.categories
    ]
    result["geopolitics"] = generate_feed(geo_items, feed_title="Personal Intelligence — Geopolitics", feed_filename="geopolitics.xml")

    # Markets feed
    market_items = [
        i for i in items
        if i.domain == Domain.MARKETS or any(c in i.categories for c in ["Indian Markets", "Global Markets", "Economy", "Central Banks"])
    ]
    result["markets"] = generate_feed(market_items, feed_title="Personal Intelligence — Markets", feed_filename="markets.xml")

    # Technology feed
    tech_items = [
        i for i in items
        if i.domain == Domain.TECHNOLOGY or "Technology" in i.categories or "Semiconductors" in i.categories
    ]
    result["technology"] = generate_feed(tech_items, feed_title="Personal Intelligence — Technology", feed_filename="technology.xml")

    # GitHub feed
    github_items = [
        i for i in items
        if i.domain == Domain.GITHUB or "GitHub" in i.categories
    ]
    result["github"] = generate_feed(github_items, feed_title="Personal Intelligence — GitHub", feed_filename="github.xml")

    return result


def _add_item(channel: Element, item: IntelligenceItem) -> None:
    """Add a single item to the RSS channel."""
    rss_item = SubElement(channel, "item")

    # Title with score prefix
    SubElement(rss_item, "title").text = format_title(item)

    # Link (prefer direct paper/github URL if available)
    item_url = item.paper_url or item.github_url or item.url
    SubElement(rss_item, "link").text = item_url

    # Description (CDATA HTML)
    description = format_description(item)
    desc_elem = SubElement(rss_item, "description")
    desc_elem.text = description

    # Stable GUID
    guid = SubElement(rss_item, "guid", isPermaLink="false")
    guid.text = hashlib.sha256(item_url.encode("utf-8")).hexdigest()[:32]

    # Publication date
    if item.published_at:
        SubElement(rss_item, "pubDate").text = _rfc822(item.published_at)

    # Categories
    for cat in item.categories[:5]:
        SubElement(rss_item, "category").text = cat

    # Source
    source_elem = SubElement(rss_item, "source", url=item_url)
    source_elem.text = item.source


def _rfc822(dt: datetime) -> str:
    """Format datetime as RFC 822 for RSS."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def _rfc822_now() -> str:
    """Current time in RFC 822."""
    return _rfc822(datetime.now(timezone.utc))


def _validate_feed(path: Path) -> bool:
    """Basic XML validation of the generated feed."""
    try:
        from lxml import etree
        with open(path, "rb") as f:
            etree.parse(f)
        return True
    except Exception as e:
        logger.error(f"[RSS] Feed validation FAILED for {path.name}: {e}")
        return False
