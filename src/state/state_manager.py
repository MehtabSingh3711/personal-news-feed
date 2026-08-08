"""Persistent state manager — tracks published items across runs."""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.config import DATA_DIR
from src.models import IntelligenceItem, StateEntry

logger = logging.getLogger(__name__)

STATE_FILE = DATA_DIR / "state.json"
PRUNE_DAYS = 30  # Remove entries older than this


class StateManager:
    """JSON-based persistent state for tracking published items."""

    def __init__(self, state_path: Path | None = None) -> None:
        self.path = state_path or STATE_FILE
        self._entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load state from disk."""
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
                logger.info(f"[STATE] Loaded {len(self._entries)} entries")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[STATE] Failed to load state: {e}")
                self._entries = {}
        else:
            logger.info("[STATE] No existing state file, starting fresh")

    def save(self) -> None:
        """Persist state to disk atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic on most OS)
        try:
            tmp_path = self.path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, default=str)
            tmp_path.replace(self.path)
            logger.info(f"[STATE] Saved {len(self._entries)} entries")
        except OSError as e:
            logger.error(f"[STATE] Failed to save state: {e}")

    def is_published(self, item_id: str) -> bool:
        """Check if an item has already been published."""
        return item_id in self._entries

    def record(self, item: IntelligenceItem) -> None:
        """Record an item as published."""
        now = datetime.now(timezone.utc).isoformat()

        if item.id in self._entries:
            # Update existing
            self._entries[item.id]["last_seen"] = now
            self._entries[item.id]["score"] = item.final_score
            self._entries[item.id]["classification"] = item.classification.value
        else:
            # New entry
            self._entries[item.id] = {
                "item_id": item.id,
                "title": item.title,
                "url": item.url,
                "first_seen": now,
                "last_seen": now,
                "score": item.final_score,
                "classification": item.classification.value,
                "cluster_id": item.cluster_id,
                "published_date": (
                    item.published_at.isoformat() if item.published_at else None
                ),
            }

    def filter_new(self, items: list[IntelligenceItem]) -> list[IntelligenceItem]:
        """Filter out already-published items."""
        new_items = [item for item in items if not self.is_published(item.id)]
        skipped = len(items) - len(new_items)
        if skipped:
            logger.info(f"[STATE] {skipped} items already published, skipped")
        return new_items

    def prune(self, max_age_days: int = PRUNE_DAYS) -> None:
        """Remove entries older than max_age_days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        cutoff_str = cutoff.isoformat()

        before = len(self._entries)
        self._entries = {
            k: v for k, v in self._entries.items()
            if v.get("last_seen", "") >= cutoff_str
        }
        pruned = before - len(self._entries)

        if pruned:
            logger.info(f"[STATE] Pruned {pruned} old entries")

    @property
    def count(self) -> int:
        return len(self._entries)
