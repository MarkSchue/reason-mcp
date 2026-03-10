"""Candidate Rule Filter — parallel dual-path retrieval.

Two independent retrieval paths run for every call and are then unioned:

  Path A (deterministic)
      Observation ID overlap + keyword overlap against ``trigger`` fields.
      Hard exclusions: domain mismatch, context_state mismatch.
      Returns each matching rule together with a *det_score* (0..1).

  Path B (semantic, opt-in via ``semantic_query``)
      Vector cosine similarity via the local ChromaDB index.
      Only applies domain exclusion — trigger keywords are irrelevant here.
      Returns each matching rule together with the actual *cosine score*.

Both paths are independent.  Neither gates the other.  A rule found by
*either* path is always included in the final candidate set.  Rules found
by both paths carry non-zero scores on both dimensions, which the compressor
uses for combined ranking.

Each returned rule has two transient score fields attached:
    ``_det_score``   — 0..1, from the deterministic path (0 = not found)
    ``_sem_score``   — 0..1, from the semantic path (0 = not found)

These fields are stripped by the compressor before LLM injection.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_kw(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s]", "", s).lower()
    return s.strip()


def _expand_kw(s: str) -> set[str]:
    norm = _normalize_kw(s)
    return set(norm.split()) | {norm}


# ---------------------------------------------------------------------------
# Path A — deterministic
# ---------------------------------------------------------------------------

def _det_candidates(
    rules: list[dict[str, Any]],
    obs_ids: set[str],
    query_kw: set[str],
    domain: str | None,
    context_state: str | None,
) -> list[tuple[dict[str, Any], float]]:
    """Return (rule, det_score) pairs for all deterministically matching rules.

    Catch-all rules (no trigger criteria) always pass with a neutral score of 0.5.
    """
    results: list[tuple[dict[str, Any], float]] = []
    for rule in rules:
        # Hard domain exclusion
        if domain and rule.get("domain") and rule["domain"] != domain:
            continue

        trigger = rule.get("trigger", {})

        # Hard context_state exclusion
        required_states: list[str] = trigger.get("context_states", [])
        if required_states and context_state not in required_states:
            continue

        trigger_obs: list[str] = trigger.get("observations", [])
        trigger_kw: set[str] = set()
        for k in trigger.get("keywords", []):
            trigger_kw |= _expand_kw(k)

        has_criteria = bool(trigger_obs) or bool(trigger_kw)
        if not has_criteria:
            # Catch-all rule — always passes, neutral score
            results.append((rule, 0.5))
            continue

        obs_match = bool(trigger_obs) and bool(obs_ids.intersection(trigger_obs))
        kw_match = bool(trigger_kw) and bool(query_kw.intersection(trigger_kw))

        if not obs_match and not kw_match:
            continue  # no deterministic signal → not in Path A

        obs_score = (
            len(obs_ids.intersection(trigger_obs)) / len(trigger_obs)
            if obs_match and trigger_obs
            else 0.0
        )
        det_score = max(obs_score, 1.0 if kw_match else 0.0)
        results.append((rule, det_score))

    return results


# ---------------------------------------------------------------------------
# Path B — semantic
# ---------------------------------------------------------------------------

def _sem_candidates(
    rules: list[dict[str, Any]],
    semantic_query: str,
    index_dir: Path,
    min_score: float,
    domain: str | None,
) -> list[tuple[dict[str, Any], float]]:
    """Return (rule, cosine_score) pairs for rules found via vector similarity.

    Trigger keywords and observation criteria are intentionally ignored — the
    embeddings operate on the full rule text, not the trigger metadata.
    """
    try:
        from reason_mcp.tools.reasoning.embedder import search_rules as _search
    except ImportError:
        logger.warning("semantic extras not installed — semantic path disabled")
        return []

    rule_by_id = {r.get("rule_id"): r for r in rules}
    try:
        hits: list[tuple[str, float]] = _search(
            semantic_query,
            index_dir,
            rules,
            top_k=len(rules),   # retrieve all; compressor applies top_k cap
            min_score=min_score,
            domain=domain,
        )
    except Exception:
        logger.exception("semantic search failed — semantic path returning empty")
        return []

    return [(rule_by_id[rid], score) for rid, score in hits if rid in rule_by_id]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def filter_candidates(
    rules: list[dict[str, Any]],
    observation_ids: set[str],
    domain: str | None = None,
    context_state: str | None = None,
    keywords: set[str] | None = None,
    semantic_query: str | None = None,
    semantic_min_score: float = 0.75,
    index_dir: Any | None = None,
) -> list[dict[str, Any]]:
    """Return the union of deterministic and semantic candidate rules.

    Both retrieval paths run independently.  A rule found by either path is
    included in the result set regardless of the other path's outcome.  Each
    returned rule has ``_det_score`` and ``_sem_score`` fields attached for
    downstream ranking by the compressor.

    Args:
        rules: Full rule list from the knowledge directory.
        observation_ids: Normalised observation IDs in the current request.
        domain: Optional domain hint — rules with a different domain are excluded.
        context_state: Optional context state — rules requiring a different state
            are excluded (deterministic path only).
        keywords: Lowercase keywords from a natural-language query, matched
            against ``trigger.keywords``.
        semantic_query: NL text to embed and match against the rule vector index.
            When omitted, only the deterministic path runs.
        semantic_min_score: Minimum cosine similarity for a semantic hit.
        index_dir: Path to the Chroma index.  Required when *semantic_query* is set.
    """
    query_kw: set[str] = set()
    if keywords:
        for k in keywords:
            query_kw |= _expand_kw(k)

    # --- Path A: deterministic ---
    det_results = _det_candidates(rules, observation_ids, query_kw, domain, context_state)
    det_by_id: dict[str, float] = {r.get("rule_id"): score for r, score in det_results}

    # --- Path B: semantic (opt-in) ---
    sem_by_id: dict[str, float] = {}
    if semantic_query and index_dir is not None:
        sem_results = _sem_candidates(
            rules,
            semantic_query,
            Path(index_dir),
            semantic_min_score,
            domain,
        )
        sem_by_id = {r.get("rule_id"): score for r, score in sem_results}

    # --- Merge: union of both paths ---
    all_ids: set[str] = set(det_by_id) | set(sem_by_id)
    rule_by_id = {r.get("rule_id"): r for r in rules}

    candidates: list[dict[str, Any]] = []
    for rule_id in all_ids:
        rule = rule_by_id.get(rule_id)
        if rule is None:
            continue
        # Attach scores for compressor ranking (stripped before LLM injection)
        rule["_det_score"] = det_by_id.get(rule_id, 0.0)
        rule["_sem_score"] = sem_by_id.get(rule_id, 0.0)
        candidates.append(rule)

    logger.info(
        "candidate filter",
        total_rules=len(rules),
        det_hits=len(det_by_id),
        sem_hits=len(sem_by_id),
        candidates=len(candidates),
        domain=domain,
    )
    return candidates
