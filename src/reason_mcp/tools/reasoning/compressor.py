"""Lean Context Injector / Relevance Compressor (REQ-003).

Enforces the "inject what is really needed, but nothing more" principle:
 - Selects top_k rules by relevance score.
 - Strips developer-internal metadata fields before returning.

Facts are no longer a separate concept.  Physical constants and domain facts
are expressed directly as conditions within rules (via natural_language or
exact condition fields) and are therefore automatically included when a rule
is selected by the compressor.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Fields that must NOT be forwarded to the LLM (internal metadata)
_STRIP_FIELDS = {"author", "updated_at", "created_at", "source", "version", "active",
                 "_det_score", "_sem_score"}


def _relevance_score(rule: dict[str, Any], observation_ids: set[str]) -> float:
    """Combined relevance heuristic: best of deterministic and semantic signals.

    Uses pre-computed ``_det_score`` and ``_sem_score`` attached by the filter.
    The higher of the two becomes the *match signal* (0..1), which is blended
    with the rule's domain-specificity score:

        relevance = match_signal × 0.6 + specificity × 0.4

    Legacy path (no attached scores): falls back to the observation-overlap
    heuristic so rules can be scored without running through filter.py.
    """
    det_score: float | None = rule.get("_det_score")
    sem_score: float = rule.get("_sem_score", 0.0)

    if det_score is not None:
        match_signal = max(det_score, sem_score)
    else:
        # Legacy / standalone path: compute from observation overlap
        trigger_obs: list[str] = rule.get("trigger", {}).get("observations", [])
        if trigger_obs and observation_ids:
            overlap = len(observation_ids.intersection(trigger_obs))
            match_signal = overlap / len(trigger_obs)
        elif not trigger_obs:
            match_signal = 0.5
        else:
            match_signal = 0.0

    confidence = rule.get("reasoning", {}).get("confidence_prior", 0.5)
    specificity = rule.get("scoring", {}).get("specificity", confidence)
    return round(match_signal * 0.6 + specificity * 0.4, 4)


def _strip_metadata(rule: dict[str, Any]) -> dict[str, Any]:
    """Remove internal fields from a rule before LLM injection."""
    return {k: v for k, v in rule.items() if k not in _STRIP_FIELDS}


def compress(
    candidates: list[dict[str, Any]],
    observation_ids: set[str],
    top_k: int,
    min_relevance: float,
) -> list[dict[str, Any]]:
    """
    Returns lean_rules: the top_k most relevant rules, stripped of internal metadata.

    Ranks candidates, applies top_k and min_relevance thresholds, and strips
    developer metadata.  Any facts embedded in rule conditions are automatically
    included as part of the rule itself.
    """
    # Score and sort
    scored = [
        (rule, _relevance_score(rule, observation_ids))
        for rule in candidates
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Apply thresholds
    filtered = [
        (rule, score)
        for rule, score in scored
        if score >= min_relevance
    ][:top_k]

    if not filtered:
        logger.info("no candidates passed relevance threshold", min=min_relevance)
        return []

    lean_rules = [_strip_metadata(rule) for rule, _ in filtered]

    # Attach relevance score as the only added field (useful for LLM)
    for (_, score), lean in zip(filtered, lean_rules):
        lean["_relevance_score"] = score

    logger.info(
        "compression complete",
        candidates=len(candidates),
        returned=len(lean_rules),
    )
    return lean_rules
