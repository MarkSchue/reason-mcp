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
                 "_sem_score"}


def _relevance_score(rule: dict[str, Any]) -> float:
    """Relevance heuristic: semantic similarity blended with domain specificity.

    Uses pre-computed ``_sem_score`` attached by the filter.  Catch-all rules
    (no semantic hit, sem_score=0.0) receive a neutral 0.5 match signal so they
    can still pass the relevance threshold.

        relevance = match_signal × 0.6 + specificity × 0.4
    """
    sem_score: float = rule.get("_sem_score", 0.0)
    # Catch-all rules (no semantic signal) get a neutral match signal
    match_signal = sem_score if sem_score > 0.0 else 0.5
    confidence = rule.get("reasoning", {}).get("confidence_prior", 0.5)
    specificity = rule.get("scoring", {}).get("specificity", confidence)
    return round(match_signal * 0.6 + specificity * 0.4, 4)


def _strip_metadata(rule: dict[str, Any]) -> dict[str, Any]:
    """Remove internal fields from a rule before LLM injection."""
    return {k: v for k, v in rule.items() if k not in _STRIP_FIELDS}


def compress(
    candidates: list[dict[str, Any]],
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
        (rule, _relevance_score(rule))
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
