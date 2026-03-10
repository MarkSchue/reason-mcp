"""Reasoning MCP tool – registers `reasoning_analyze_context` on the server.

Pipeline (Lean Context Injection):
  observations / keywords  →  [Pruner]  →  [Normalizer]  →  [Candidate Filter]
  →  [Compressor / top_k]  →  #Rule-formatted context bundle  →  Host LLM

Three retrieval paths run in parallel for every request:
  Structured  – caller supplies observation IDs from sensors/telemetry.
  Keyword     – caller (Host LLM) extracts keywords from a natural-language query
               and passes them; the filter matches them against trigger.keywords.
  Semantic    – always active; embeds the query string and searches the local
               Chroma vector index for closest-matching rule chunks.
               Requires the ``[semantic]`` extras (gracefully skipped if absent).

Results from all three paths are unioned and ranked together.  A rule fires on
any hit from any path.  Neither path gates the others.

Facts are embedded directly in rule conditions — no separate resolution step.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from reason_mcp.config import config
from reason_mcp.knowledge.loader import get_knowledge
from reason_mcp.session_log import SessionLog
from reason_mcp.tools.reasoning.compressor import compress
from reason_mcp.tools.reasoning.filter import filter_candidates
from reason_mcp.tools.reasoning.normalizer import load_aliases, normalize
from reason_mcp.tools.reasoning.pruner import prune

logger = structlog.get_logger(__name__)


def _render_rules_as_text(lean_rules: list[dict[str, Any]]) -> str:
    """Render the selected rules as a human-readable, LLM-friendly text block.

    Format (mirrors the target from prompts.md):

        #Rule 1: <conditions.natural_language or exact predicate summary>
        **Reason:** <possible causes>
        **Recommendation:** <action>

        #Rule 2: ...
    """
    blocks: list[str] = []
    for i, rule in enumerate(lean_rules, start=1):
        conditions = rule.get("conditions", {})
        nl = conditions.get("natural_language", "")
        exact = conditions.get("exact", [])

        if nl:
            rule_text = nl
        elif exact:
            rule_text = " AND ".join(
                f"{c.get('left')} {c.get('op')} {c.get('right')}" for c in exact
            )
        else:
            rule_text = "(no condition text)"

        lines = [f"#Rule {i}: {rule_text}"]

        causes = rule.get("reasoning", {}).get("possible_causes", [])
        if causes:
            lines.append(f"**Reason:** {', '.join(causes)}.")

        action = rule.get("recommendation", {}).get("action", "")
        if action:
            lines.append(f"**Recommendation:** {action}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def register(mcp: FastMCP) -> None:
    """Attach the reasoning tool to the MCP server instance."""

    @mcp.tool(
        name="reasoning_analyze_context",
        description=(
            "Retrieve domain-specific rules relevant to the given observations or keywords. "
            "Three parallel retrieval paths: (1) structured — pass observation IDs from "
            "sensors/telemetry; (2) keyword — pass keywords extracted from a natural-language "
            "query (e.g. ['car', 'weight']); (3) semantic — always active, vector-similarity "
            "search over embedded rule chunks. All paths run in parallel and results are unioned. "
            "Returns a lean, #Rule-formatted knowledge bundle so the calling LLM can reason "
            "about the context without needing prior domain training."
        ),
    )
    def analyze_context(
        request_id: str,
        timestamp: str,
        observations: list[dict[str, Any]],
        domain: str | None = None,
        subject_id: str | None = None,
        context_state: str | None = None,
        keywords: list[str] | None = None,
        top_k: int | None = None,
        min_relevance: float | None = None,
        semantic_min_score: float = 0.75,
    ) -> dict[str, Any]:
        """
        Args:
            request_id: Caller-generated ID for traceability.
            timestamp: ISO 8601 timestamp of the observation batch.
            observations: List of {observation_id, value, unit?, quality?, ...}.
                          May be empty when using keyword-only retrieval.
            domain: Optional domain hint (e.g. "fleet_tracking", "chemistry").
            subject_id: Optional subject under analysis.
            context_state: Optional high-level system state (e.g. "PRODUCTION").
            keywords: Optional list of lowercase keywords extracted from a natural-language
                      query (e.g. ["car", "weight"]).  Used for keyword and semantic matching.
            top_k: Max rules to inject (default: REASON_DEFAULT_TOP_K env var).
            min_relevance: Minimum relevance score 0..1 (default: REASON_MIN_RELEVANCE).
            semantic_min_score: Minimum cosine similarity for a semantic hit (default 0.75).
        """
        t0 = time.monotonic()
        trace_id = str(uuid.uuid4())[:8]

        # --- Session log (opt-in via REASON_LOG_REQUESTS) ---
        slog = SessionLog("reasoning_analyze_context", request_id, timestamp)
        if config.log_requests:
            slog.record_request({
                "request_id": request_id,
                "timestamp": timestamp,
                "observations": observations,
                "domain": domain,
                "subject_id": subject_id,
                "context_state": context_state,
                "keywords": keywords,
                "top_k": top_k,
                "min_relevance": min_relevance,
                "semantic_min_score": semantic_min_score,
            })

        effective_top_k = top_k if top_k is not None else config.default_top_k
        effective_min_rel = min_relevance if min_relevance is not None else config.min_relevance

        # --- Load knowledge (cached) ---
        rules = get_knowledge(config.knowledge_dir)
        aliases = load_aliases(config.knowledge_dir)

        # --- Pipeline ---
        # 1. Prune nominal observations (no-op when observations list is empty)
        pruned_obs = prune(observations) if observations else []
        if config.log_requests:
            slog.record_step("Step 1 — Pruner", {
                "input_count": len(observations) if observations else 0,
                "pruned_count": len(pruned_obs),
                "pruned_observations": pruned_obs,
            })

        # 2. Normalise observation IDs via taxonomy aliases
        normalised_obs = normalize(pruned_obs, aliases)
        obs_ids = {o["observation_id"] for o in normalised_obs}
        if config.log_requests:
            slog.record_step("Step 2 — Normalizer", {
                "normalised_observations": normalised_obs,
                "obs_ids": sorted(obs_ids),
            })

        # 3. Normalise keywords to lowercase for case-insensitive matching
        kw_set = {k.lower() for k in keywords} if keywords else set()
        if config.log_requests:
            slog.record_step("Step 3 — Keyword extraction", {
                "input_keywords": keywords or [],
                "normalised_keyword_set": sorted(kw_set),
            })

        # 4. Build semantic query text — semantic path always runs in parallel
        nl_parts: list[str] = []
        if keywords:
            nl_parts.extend(keywords)
        for obs in (observations or []):
            nl_parts.append(str(obs.get("observation_id", "")))
            nl_parts.append(str(obs.get("value", "")))
        effective_semantic_query: str | None = " ".join(nl_parts) if nl_parts else None
        effective_index_dir: str = str(config.knowledge_dir / ".semantic_index")
        if config.log_requests:
            slog.record_step("Step 4 — Semantic query construction", {
                "effective_semantic_query": effective_semantic_query,
                "index_dir": effective_index_dir,
                "semantic_min_score": semantic_min_score,
            })

        # 5. Filter candidate rules (observations OR keywords OR semantic)
        candidates = filter_candidates(
            rules,
            obs_ids,
            domain=domain,
            context_state=context_state,
            keywords=kw_set,
            semantic_query=effective_semantic_query,
            semantic_min_score=semantic_min_score,
            index_dir=effective_index_dir,
        )
        if config.log_requests:
            _path_a = [
                {"rule_id": c.get("rule_id"), "det_score": round(c.get("_det_score", 0), 4)}
                for c in candidates if c.get("_det_score", 0) > 0
            ]
            _path_b = [
                {"rule_id": c.get("rule_id"), "sem_score": round(c.get("_sem_score", 0), 4)}
                for c in candidates if c.get("_sem_score", 0) > 0
            ]
            _both = sorted(
                c.get("rule_id") for c in candidates
                if c.get("_det_score", 0) > 0 and c.get("_sem_score", 0) > 0
            )
            slog.record_step("Step 5A — Path A (Deterministic retrieval)", {
                "matched_count": len(_path_a),
                "rules": _path_a,
            })
            slog.record_step("Step 5B — Path B (Semantic retrieval)", {
                "query": effective_semantic_query,
                "matched_count": len(_path_b),
                "rules": _path_b,
            })
            slog.record_step("Step 5C — Union & score annotation", {
                "total_candidates": len(candidates),
                "found_by_both_paths": _both,
                "all_candidates": [
                    {
                        "rule_id": c.get("rule_id"),
                        "det_score": round(c.get("_det_score", 0), 4),
                        "sem_score": round(c.get("_sem_score", 0), 4),
                    }
                    for c in candidates
                ],
            })

        # 6. Rank, compress to top_k, strip metadata
        lean_rules = compress(
            candidates,
            obs_ids,
            top_k=effective_top_k,
            min_relevance=effective_min_rel,
        )
        if config.log_requests:
            slog.record_step("Step 6 — Compressor (top-k ranking)", {
                "top_k": effective_top_k,
                "min_relevance": effective_min_rel,
                "lean_rules_count": len(lean_rules),
                "selected_rule_ids": [r.get("rule_id") for r in lean_rules],
            })

        # 7. Render rules as #Rule N: formatted text for direct LLM injection
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        if lean_rules:
            summary = _render_rules_as_text(lean_rules)
            status = "ok"
        else:
            summary = "No domain rules matched the current observations or keywords."
            status = "partial"

        result = {
            "request_id": request_id,
            "status": status,
            "result": {
                "candidate_knowledge": lean_rules,
                "summary_for_llm": summary,
            },
            "meta": {
                "knowledge_version": "json-file",
                "latency_ms": latency_ms,
                "candidate_count": len(candidates),
                "matched_count": len(lean_rules),
                "applied_policies": [
                    "zero_value_pruning",
                    "lean_context_injection",
                    "semantic_retrieval",
                ],
                "trace_id": trace_id,
            },
        }
        if config.log_requests:
            slog.record_decision(
                f"status={status!r}: {len(lean_rules)} rule(s) selected from "
                f"{len(candidates)} candidate(s) (top_k={effective_top_k}, "
                f"min_relevance={effective_min_rel})."
            )
            slog.record_result(result)
            log_path = slog.write(config.output_dir)
            logger.info("session_log_written", path=str(log_path), request_id=request_id)
        return result
