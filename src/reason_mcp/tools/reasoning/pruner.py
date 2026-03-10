"""Zero-Value Pruner (REQ-016).

Strips observations that fall within expected nominal baselines so the LLM
context window only receives anomalous / relevant data points.
"""

from __future__ import annotations

import statistics
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def prune(
    observations: list[dict[str, Any]],
    nominal_ranges: dict[str, tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    """Return only the observations that look anomalous.

    Strategy (in order of precedence):
    1. If *nominal_ranges* contains an entry for an observation_id, use
       explicit [low, high] bounds.
    2. For purely numeric arrays with ≥ 5 values, apply a simple
       z-score filter (|z| > 2) to detect statistical outliers.
    3. Non-numeric values (strings, booleans) are always kept – the LLM
       can reason about them.
    """
    nominal_ranges = nominal_ranges or {}
    numeric_values = [
        float(o["value"]) for o in observations if isinstance(o.get("value"), (int, float))
    ]

    # Compute population statistics for z-score fallback
    mean: float | None = None
    stdev: float | None = None
    if len(numeric_values) >= 5:
        mean = statistics.mean(numeric_values)
        stdev = statistics.pstdev(numeric_values) or None

    pruned: list[dict[str, Any]] = []
    for obs in observations:
        oid = obs["observation_id"]
        val = obs.get("value")

        # Non-numeric: always retain
        if not isinstance(val, (int, float)):
            pruned.append(obs)
            continue

        fval = float(val)

        # Explicit nominal range check
        if oid in nominal_ranges:
            low, high = nominal_ranges[oid]
            if low <= fval <= high:
                logger.debug("pruned nominal observation", id=oid, value=fval)
                continue
            pruned.append(obs)
            continue

        # Z-score fallback
        if mean is not None and stdev is not None:
            z = abs(fval - mean) / stdev
            if z <= 2.0:
                logger.debug("pruned z-nominal observation", id=oid, z=round(z, 2))
                continue

        pruned.append(obs)

    logger.info("pruning complete", before=len(observations), after=len(pruned))
    return pruned
