"""Semantic Normalizer (REQ-010).

Maps raw proprietary observation IDs (e.g. ``DP_042``) to canonical concept
keys used in rules.  Aliases are loaded from
``knowledge_dir/taxonomy/aliases.json``.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

AliasMap = dict[str, str]  # raw_key -> canonical_key


def load_aliases() -> AliasMap:
    """Return an empty alias map.

    Alias-based normalisation has been retired.  Observation IDs are now
    expected to be globally unique canonical keys by the time they reach the
    reasoning pipeline.  This function is kept to preserve call-site
    compatibility but always returns an empty dict (a pass-through).
    """
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
