"""Semantic Normalizer (REQ-010).

Maps raw proprietary observation IDs (e.g. ``DP_042``) to canonical concept
keys used in rules.  Aliases are loaded from
``knowledge_dir/taxonomy/aliases.json``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson
import structlog

logger = structlog.get_logger(__name__)

AliasMap = dict[str, str]  # raw_key -> canonical_key


def load_aliases(knowledge_dir: Path) -> AliasMap:
    """Load concept aliases from taxonomy/aliases.json (optional file)."""
    path = knowledge_dir / "taxonomy" / "aliases.json"
    if not path.exists():
        return {}
    try:
        data: dict[str, str] = orjson.loads(path.read_bytes())
        logger.debug("aliases loaded", count=len(data))
        return data
    except Exception:
        logger.exception("failed to load aliases", path=str(path))
        return {}


def normalize(
    observations: list[dict[str, Any]],
    aliases: AliasMap,
) -> list[dict[str, Any]]:
    """Replace observation_id values using the alias map where a mapping exists."""
    if not aliases:
        return observations
    normalised = []
    for obs in observations:
        oid = obs["observation_id"]
        canonical = aliases.get(oid, oid)
        if canonical != oid:
            logger.debug("normalised observation id", from_=oid, to=canonical)
            obs = {**obs, "observation_id": canonical}
        normalised.append(obs)
    return normalised
