"""Editorial-style HTML brief formatter for RSS readers (NetNewsWire / Reeder)."""

from __future__ import annotations

import html
import re

from src.models import Classification, Domain, IntelligenceItem, SourceType


def format_description(item: IntelligenceItem) -> str:
    """Format an item into an editorial-style intelligence brief."""
    parts: list[str] = []

    # 1. Headline / Section Header for GitHub items
    if item.domain == Domain.GITHUB:
        parts.append("<h3>WHAT IT IS</h3>")
    else:
        parts.append("<h3>WHAT HAPPENED</h3>")

    what_text = _format_what_happened(item)
    parts.append(f"<p>{html.escape(what_text)}</p>")

    # 2. WHY IT MATTERS
    parts.append("<h3>WHY IT MATTERS</h3>")
    why_text = _format_why_it_matters(item)
    parts.append(f"<p>{html.escape(why_text)}</p>")

    # 3. IMPORTANCE
    class_label = _classification_label(item.classification)
    parts.append(
        f"<h3>IMPORTANCE</h3>"
        f"<p><strong>{item.final_score:.1f}/10</strong> · {class_label}</p>"
    )

    # 4. CATEGORY
    if item.categories:
        cats = " / ".join(html.escape(c) for c in item.categories[:5])
        parts.append(f"<h3>CATEGORY</h3><p>{cats}</p>")

    # 5. SIGNALS
    signals = _format_signals(item)
    if signals:
        parts.append(f"<h3>SIGNALS</h3><p>{signals}</p>")

    # 6. DIRECT SOURCE LINKS (clickable <a> tags)
    links_html = _format_direct_links(item)
    if links_html:
        parts.append(f"<h3>SOURCES & LINKS</h3>{links_html}")

    return "\n".join(parts)


def _format_what_happened(item: IntelligenceItem) -> str:
    """Produce 1–3 clean sentences explaining what happened or what the repo is."""
    if item.what_happened:
        return item.what_happened

    summary = item.summary or item.title
    # Clean up raw HTML / whitespace
    clean = re.sub(r"<[^>]+>", " ", summary)
    clean = re.sub(r"\s+", " ", clean).strip()

    # Truncate at 2-3 complete sentences
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    if len(sentences) > 3:
        clean = " ".join(sentences[:3])

    if len(clean) > 400:
        clean = clean[:397].rsplit(" ", 1)[0] + "..."

    return clean


def _format_why_it_matters(item: IntelligenceItem) -> str:
    """Produce 1–3 sentences explaining significance."""
    if item.why_it_matters:
        return item.why_it_matters

    if item.llm_judgment and item.llm_judgment.reason:
        return item.llm_judgment.reason

    title_lower = item.title.lower()
    summary_lower = (item.summary or "").lower()
    text = f"{title_lower} {summary_lower}"

    if item.domain == Domain.GITHUB:
        if item.paper_url:
            return "Official open-source implementation accompanying a research paper. High value for AI developers and researchers."
        if item.github_stars > 1000:
            return f"Rapidly growing open-source project ({item.github_stars:,} stars) with active community adoption."
        return "Promising open-source AI project advancing state-of-the-art tooling."

    elif item.domain == Domain.AI_RESEARCH:
        if any(k in text for k in ["llm", "large language", "reasoning"]):
            return "Advances fundamental language model capabilities, reasoning efficiency, or training methodology."
        if any(k in text for k in ["agent", "agentic"]):
            return "Improves autonomous AI agent workflows, tool use, or planning architectures."
        if any(k in text for k in ["rag", "retrieval"]):
            return "Enhances retrieval-augmented generation accuracy, knowledge grounding, or context window utilization."
        if any(k in text for k in ["multimodal", "vision"]):
            return "Extends vision-language integration for complex real-world reasoning and interaction."
        return "Presents novel methodological contributions or empirical benchmarks for AI research."

    elif item.domain == Domain.GEOPOLITICS or item.domain == Domain.INDIA:
        if any(k in text for k in ["trade", "tariff", "agreement"]):
            return "Materially affects bilateral economic policy, trade flows, and international diplomatic relations."
        if any(k in text for k in ["military", "defense", "border", "conflict"]):
            return "Carries significant international security and regional stability implications."
        if any(k in text for k in ["rbi", "budget", "court", "parliament"]):
            return "Key legislative, judicial, or monetary policy action with broad national implications."
        return "Represents a material strategic development in geopolitics and international affairs."

    elif item.domain == Domain.MARKETS:
        if any(k in text for k in ["fed", "rbi", "rate", "inflation", "cpi"]):
            return "Directly impacts monetary policy expectations, interest rate trajectories, and global asset pricing."
        if any(k in text for k in ["earnings", "gdp", "employment"]):
            return "Key macroeconomic indicator influencing market sentiment and sector allocations."
        return "Consequential financial market shift with broader economic ramifications."

    elif item.domain == Domain.TECHNOLOGY:
        if any(k in text for k in ["chip", "gpu", "cpu", "semiconductor"]):
            return "Major hardware architecture release directly impacting AI compute supply and semiconductor competition."
        if any(k in text for k in ["launch", "unveil", "announce"]):
            return "Key commercial product announcement setting industry standard for enterprise and developer tools."
        return "Strategic technology milestone impacting enterprise platform ecosystems."

    return "Consequential event worth monitoring for strategic and market implications."


def _format_signals(item: IntelligenceItem) -> str:
    """Format community/academic signals cleanly."""
    parts: list[str] = []

    if item.domain == Domain.GITHUB:
        if item.github_growth:
            parts.append(item.github_growth)
        elif item.github_stars > 0:
            parts.append(f"{item.github_stars:,} ★")
        if item.github_forks > 0:
            parts.append(f"{item.github_forks:,} forks")
    else:
        if item.hf_upvotes > 0:
            parts.append(f"HF: {item.hf_upvotes} upvotes")
        if item.github_stars > 0:
            parts.append(f"GitHub: {item.github_stars:,} ★")
        if item.citation_count > 0:
            parts.append(f"Citations: {item.citation_count}")
        if item.venue:
            parts.append(f"Venue: {html.escape(item.venue)}")

    return " · ".join(parts)


def _format_direct_links(item: IntelligenceItem) -> str:
    """Format clean, clickable HTML links (<a href="...">)."""
    links: list[str] = []

    paper_target = item.paper_url or (f"https://arxiv.org/abs/{item.arxiv_id}" if item.arxiv_id else None)
    github_target = item.github_url

    if item.domain == Domain.GITHUB:
        if github_target:
            links.append(f'<a href="{html.escape(github_target)}" target="_blank" rel="noopener"><strong>View Repository →</strong></a>')
        if paper_target:
            links.append(f'<a href="{html.escape(paper_target)}" target="_blank" rel="noopener">Read Paper →</a>')

    elif item.domain == Domain.AI_RESEARCH:
        if paper_target:
            links.append(f'<a href="{html.escape(paper_target)}" target="_blank" rel="noopener"><strong>Read Paper →</strong></a>')
        elif item.url:
            links.append(f'<a href="{html.escape(item.url)}" target="_blank" rel="noopener"><strong>Read Paper →</strong></a>')

        if github_target:
            links.append(f'<a href="{html.escape(github_target)}" target="_blank" rel="noopener">Official Code →</a>')

    elif item.source_type == SourceType.OFFICIAL_COMPANY:
        if item.url:
            links.append(f'<a href="{html.escape(item.url)}" target="_blank" rel="noopener"><strong>Official Announcement →</strong></a>')

    else:
        # News / Geopolitics / Markets
        if item.url:
            source_name = html.escape(item.source)
            links.append(f'<a href="{html.escape(item.url)}" target="_blank" rel="noopener"><strong>Read Full Article ({source_name}) →</strong></a>')

    # Multi-source coverage links
    coverage_links: list[str] = []
    if item.clustered_urls:
        for s_name, s_url in item.clustered_urls[:3]:
            if s_url != item.url:
                coverage_links.append(f'<a href="{html.escape(s_url)}" target="_blank" rel="noopener">{html.escape(s_name)}</a>')

    res = "<p>" + " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(links) + "</p>" if links else ""
    if coverage_links:
        res += f"<p><em>Other Coverage:</em> {' · '.join(coverage_links)}</p>"

    return res


def _classification_label(classification: Classification) -> str:
    """Human-readable classification label."""
    labels = {
        Classification.MUST_READ: "🔴 MUST READ",
        Classification.WORTH_KNOWING: "🟡 WORTH KNOWING",
        Classification.DISCARDED: "⚪ DISCARDED",
    }
    return labels.get(classification, "UNKNOWN")


def format_title(item: IntelligenceItem) -> str:
    """Format title with score prefix."""
    return f"[{item.final_score:.1f}] {item.title}"
