"""JSON-based knowledge loader with in-process LRU cache.

Loads all rule packs (rules/*.json) from the configured REASON_KNOWLEDGE_DIR.
Uses `watchfiles` to detect changes and invalidate the cache automatically
during development.

Design principle: the loader is read-only and domain-agnostic.  Different
project deployments simply point REASON_KNOWLEDGE_DIR at their own folder.

Facts are expressed directly as conditions within rules (natural_language or
exact conditions) — there is no separate facts registry.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import orjson
import structlog

logger = structlog.get_logger(__name__)

_lock = threading.Lock()


def _read_json(path: Path) -> Any:
    return orjson.loads(path.read_bytes())


def load_rules(knowledge_dir: Path) -> list[dict[str, Any]]:
    """Return every active rule from rules/*.json under *knowledge_dir*."""
    rules: list[dict[str, Any]] = []
    rules_dir = knowledge_dir / "rules"
    if not rules_dir.exists():
        logger.warning("rules directory not found", path=str(rules_dir))
        return rules
    for path in sorted(rules_dir.glob("*.json")):
        try:
            data = _read_json(path)
            items = data if isinstance(data, list) else data.get("rules", [data])
            active = [r for r in items if r.get("active", True)]
            rules.extend(active)
            logger.debug("loaded rules", file=path.name, count=len(active))
        except Exception:
            logger.exception("failed to load rule file", path=str(path))

    # Warn on duplicate rule_ids across files — they cause silent data loss in
    # the filter merge step and duplicate chunk errors in the semantic index.
    from collections import Counter
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
def _cached_load(knowledge_dir_str: str) -> list[dict[str, Any]]:
    """Cached loader keyed by directory string. Invalidate by calling cache_clear()."""
    return load_rules(Path(knowledge_dir_str))


def get_knowledge(knowledge_dir: Path) -> list[dict[str, Any]]:
    """Return the list of active rules for *knowledge_dir*, using the in-process cache.

    Facts are no longer a separate concept — physical constants and domain facts
    are expressed directly as conditions within rules.
    """
    return _cached_load(str(knowledge_dir))


def invalidate_cache() -> None:
    """Force reload on next call (used by file-watcher or tests).

    Also clears the semantic vector index so Stage 2 retrieval stays in sync
    with freshly loaded rules.
    """
    _cached_load.cache_clear()

    # Best-effort: clear semantic index if it has been built.
    # Import config here (not at module top) to avoid circular imports.
    try:
        from reason_mcp.config import config
        from reason_mcp.tools.reasoning.embedder import invalidate_semantic_index

        invalidate_semantic_index(config.knowledge_dir / ".semantic_index")
    except Exception:
        pass  # semantic extras not installed or index not yet built

    logger.info("knowledge cache invalidated")
