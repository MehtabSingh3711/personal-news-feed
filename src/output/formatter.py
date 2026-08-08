"""HTML description formatter optimized for Reeder on iPhone."""

from __future__ import annotations

import html

from src.models import Classification, IntelligenceItem


def format_description(item: IntelligenceItem) -> str:
    """Format the RSS item description as clean HTML for Reeder.

    Structure:
      WHAT HAPPENED
      WHY IT MATTERS (from summary)
      IMPORTANCE score
      CLASSIFICATION
      CATEGORY
      SOURCES
      SIGNALS (if any)
    """
    parts: list[str] = []

    # What happened
    parts.append("<h3>WHAT HAPPENED</h3>")
    if item.summary:
        # Escape any user-generated content for security
        safe_summary = html.escape(item.summary)
        parts.append(f"<p>{safe_summary}</p>")
    else:
        parts.append(f"<p>{html.escape(item.title)}</p>")

    # Importance
    classification_label = _classification_label(item.classification)
    parts.append(
        f"<h3>IMPORTANCE</h3>"
        f"<p><strong>{item.final_score:.1f}/10</strong> — {classification_label}</p>"
    )

    # Categories
    if item.categories:
        cats = " / ".join(html.escape(c) for c in item.categories[:5])
        parts.append(f"<h3>CATEGORY</h3><p>{cats}</p>")

    # Sources
    sources = [html.escape(item.source)]
    for s in item.cluster_sources[:5]:
        sources.append(html.escape(s))
    if len(sources) > 1:
        parts.append(f"<h3>SOURCES</h3><p>{', '.join(sources)}</p>")

    # Signals (community/academic)
    signals: list[str] = []
    if item.hf_upvotes > 0:
        signals.append(f"HF: {item.hf_upvotes} upvotes")
    if item.github_stars > 0:
        signals.append(f"GitHub: {item.github_stars:,} stars")
    if item.citation_count > 0:
        signals.append(f"Citations: {item.citation_count}")
    if item.venue:
        signals.append(f"Venue: {html.escape(item.venue)}")

    if signals:
        parts.append(f"<h3>SIGNALS</h3><p>{' · '.join(signals)}</p>")

    # LLM reason (if available)
    if item.llm_judgment and item.llm_judgment.reason:
        reason = html.escape(item.llm_judgment.reason)
        parts.append(f"<h3>ANALYSIS</h3><p><em>{reason}</em></p>")

    return "\n".join(parts)


def _classification_label(classification: Classification) -> str:
    """Human-readable classification label."""
    labels = {
        Classification.MUST_READ: "🔴 MUST READ",
        Classification.WORTH_KNOWING: "🟡 WORTH KNOWING",
        Classification.DISCARDED: "⚪ DISCARDED",
    }
    return labels.get(classification, "UNKNOWN")


def format_title(item: IntelligenceItem) -> str:
    """Format the RSS item title with score prefix."""
    return f"[{item.final_score:.1f}] {item.title}"
