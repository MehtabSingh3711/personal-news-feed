"""Pydantic models for the Personal Intelligence Engine."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Priority(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceType(str, Enum):
    RESEARCH = "research"
    NEWS = "news"
    FINANCE = "finance"
    OFFICIAL_COMPANY = "official_company"


class Domain(str, Enum):
    AI_RESEARCH = "ai_research"
    GEOPOLITICS = "geopolitics"
    INDIA = "india"
    MARKETS = "markets"
    TECHNOLOGY = "technology"


class Classification(str, Enum):
    MUST_READ = "must_read"
    WORTH_KNOWING = "worth_knowing"
    DISCARDED = "discarded"


class SourceConfig(BaseModel):
    """Configuration for a single RSS/API source."""
    name: str
    url: str
    type: SourceType
    priority: Priority
    quality_score: float = 0.80
    enabled: bool = True


class LLMJudgment(BaseModel):
    """Result from the LLM second-stage evaluator."""
    importance: float = 0.0
    novelty: float = 0.0
    technical_significance: float = 0.0
    economic_significance: float = 0.0
    geopolitical_significance: float = 0.0
    noise_penalty: float = 0.0
    decision: str = "worth_knowing"
    reason: str = ""
    raw_score: float = 0.0


class IntelligenceItem(BaseModel):
    """Normalized data model for every item in the pipeline."""
    id: str = ""
    title: str = ""
    url: str = ""
    summary: str | None = None
    published_at: datetime | None = None
    source: str = ""
    source_type: SourceType = SourceType.NEWS
    domain: Domain = Domain.GEOPOLITICS
    categories: list[str] = Field(default_factory=list)

    # Academic identifiers
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    github_url: str | None = None

    # Authors / venue
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None

    # Score components
    relevance_score: float = 0.0
    importance_score: float = 0.0
    community_score: float = 0.0
    academic_score: float = 0.0
    source_score: float = 0.0
    recency_score: float = 0.0
    noise_penalty: float = 0.0

    # Community signals (raw)
    hf_upvotes: int = 0
    github_stars: int = 0
    github_forks: int = 0
    citation_count: int = 0

    # Final output
    final_score: float = 0.0
    deterministic_score: float = 0.0
    llm_score: float | None = None
    classification: Classification = Classification.DISCARDED

    # LLM evaluation
    llm_judgment: LLMJudgment | None = None

    # Cluster tracking
    cluster_id: str | None = None
    cluster_sources: list[str] = Field(default_factory=list)

    # Metadata
    raw_content: str | None = None


class StoryCluster(BaseModel):
    """A cluster of items reporting the same real-world event."""
    cluster_id: str = ""
    canonical_title: str = ""
    canonical_url: str = ""
    domain: Domain = Domain.GEOPOLITICS
    items: list[IntelligenceItem] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    best_item: IntelligenceItem | None = None
    published_at: datetime | None = None


class StateEntry(BaseModel):
    """Persistent state for a published item."""
    item_id: str
    title: str
    url: str
    first_seen: datetime
    last_seen: datetime
    score: float
    classification: str
    cluster_id: str | None = None
    published_date: datetime | None = None
