"""RSS 2.0 feed generator with validation."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from src.config import PROJECT_ROOT
from src.models import Classification, IntelligenceItem
from src.output.formatter import format_description, format_title

logger = logging.getLogger(__name__)

FEED_FILE = PROJECT_ROOT / "feed.xml"
FEED_TITLE = "Personal Intelligence"
FEED_DESCRIPTION = (
    "High-signal intelligence briefing: AI research, geopolitics, "
    "financial markets, and major technology announcements."
)
FEED_LINK = "https://github.com"  # Updated when deployed


def generate_feed(
    items: list[IntelligenceItem],
    output_path: Path | None = None,
) -> Path:
    """Generate a valid RSS 2.0 feed from scored and classified items.

    Only includes items classified as MUST_READ or WORTH_KNOWING.
    Sorted by final_score descending.
    """
    path = output_path or FEED_FILE

    # Filter to publishable items only
    publishable = [
        item for item in items
        if item.classification in (Classification.MUST_READ, Classification.WORTH_KNOWING)
    ]

    # Sort by score descending
    publishable.sort(key=lambda x: x.final_score, reverse=True)

    logger.info(f"[RSS] Generating feed with {len(publishable)} items")

    # Build RSS XML
    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = FEED_TITLE
    SubElement(channel, "description").text = FEED_DESCRIPTION
    SubElement(channel, "link").text = FEED_LINK
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "lastBuildDate").text = _rfc822_now()
    SubElement(channel, "generator").text = "PersonalIntelligenceEngine/1.0"

    # Add self-referencing atom link
    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", FEED_LINK + "/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    for item in publishable:
        _add_item(channel, item)

    # Serialize to pretty-printed XML
    xml_bytes = tostring(rss, encoding="unicode")
    xml_str = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding=None)

    # minidom adds an extra XML declaration, ensure we have clean output
    lines = xml_str.split("\n")
    # Keep the declaration and the rest
    output = "\n".join(lines)

    # Write to file
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(output)

    # Validate
    _validate_feed(path)

    logger.info(f"[RSS] Feed written to {path}")
    return path


def _add_item(channel: Element, item: IntelligenceItem) -> None:
    """Add a single item to the RSS channel."""
    rss_item = SubElement(channel, "item")

    # Title with score prefix
    SubElement(rss_item, "title").text = format_title(item)

    # Link
    SubElement(rss_item, "link").text = item.url

    # Description (CDATA-safe HTML)
    description = format_description(item)
    desc_elem = SubElement(rss_item, "description")
    desc_elem.text = description

    # Stable GUID based on URL
    guid = SubElement(rss_item, "guid", isPermaLink="false")
    guid.text = hashlib.sha256(item.url.encode("utf-8")).hexdigest()[:32]

    # Publication date
    if item.published_at:
        SubElement(rss_item, "pubDate").text = _rfc822(item.published_at)

    # Categories
    for cat in item.categories[:5]:
        SubElement(rss_item, "category").text = cat

    # Source
    source_elem = SubElement(rss_item, "source", url=item.url)
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
        logger.info("[RSS] Feed XML validation passed")
        return True
    except ImportError:
        logger.warning("[RSS] lxml not available, skipping XML validation")
        return True
    except Exception as e:
        logger.error(f"[RSS] Feed validation FAILED: {e}")
        return False
