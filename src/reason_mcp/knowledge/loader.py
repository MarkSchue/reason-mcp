"""ArangoDB-backed knowledge loader with in-process LRU cache.

Loads all active rule documents from the ArangoDB ``rules`` collection.
The cache key is derived from the connection parameters so that different
deployments pointing at different databases each get their own cache entry.

Design principle: the loader is read-only and domain-agnostic.  Domain
knowledge is stored in the ArangoDB ``rules`` collection, seeded via
``scripts/seed_arango.py``.
"""

from __future__ import annotations

import threading
from collections import Counter
from functools import lru_cache
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_lock = threading.Lock()


def load_rules() -> list[dict[str, Any]]:
    """Return every active rule from the ArangoDB rules collection."""
    from reason_mcp.knowledge.arango_client import get_all_rules

    rules = get_all_rules()

    # Warn on duplicate rule_ids — they cause silent data loss in the filter
    # merge step when multiple rules share the same ID.
    id_counts = Counter(r.get("rule_id") for r in rules)
    dupes = [rid for rid, n in id_counts.items() if n > 1]
    if dupes:
        logger.warning(
            "duplicate rule_ids detected — use globally unique IDs across all "
            "knowledge files to avoid cross-domain rule substitution",
            duplicates=dupes,
        )

    return rules


@lru_cache(maxsize=4)
def _cached_load(arango_url: str, arango_db: str, rules_coll: str) -> list[dict[str, Any]]:
    """Cached loader keyed by connection parameters.  Invalidate by calling cache_clear()."""
    return load_rules()


def get_knowledge() -> list[dict[str, Any]]:
    """Return the list of active rules, using the in-process cache.

    Facts are no longer a separate concept — physical constants and domain facts
    are expressed directly as conditions within rules.
    """
    from reason_mcp.config import config

    return _cached_load(config.arango_url, config.arango_db, config.arango_rules_coll)


def invalidate_cache() -> None:
    """Force reload on next call (used by tests or after seed script runs)."""
    _cached_load.cache_clear()
    logger.info("knowledge cache invalidated")

