"""Reasoning MCP tool – registers `reasoning_analyze_context` on the server.

Pipeline (Lean Context Injection):
  observations / keywords  →  [Pruner]  →  [Normalizer]  →  [Candidate Filter]
  →  [Compressor / top_k]  →  #Rule-formatted context bundle  →  Host LLM

Three retrieval paths:
  Structured  – caller supplies observation IDs from sensors/telemetry.
  Keyword     – caller (Host LLM) extracts keywords from a natural-language query
               and passes them; the filter matches them against trigger.keywords.
  Semantic    – opt-in (semantic_search=True); embeds the query string and
               searches the local Chroma vector index for closest-matching rule chunks.
               Requires the ``[semantic]`` extras.

All three paths can be combined; a rule fires on any hit.

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
            "Supports two retrieval paths: (1) structured — pass observation IDs from "
            "sensors/telemetry; (2) semantic — pass keywords extracted from a natural-language "
            "query (e.g. ['car', 'weight']). Both can be combined. "
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
        semantic_search: bool = False,
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
                      query (e.g. ["car", "weight"]).  Used for semantic rule matching.
            top_k: Max rules to inject (default: REASON_DEFAULT_TOP_K env var).
            min_relevance: Minimum relevance score 0..1 (default: REASON_MIN_RELEVANCE).
            semantic_search: When True, augments Stage 1 with vector-similarity search
                             over the local Chroma rule index (requires [semantic] extras).
            semantic_min_score: Minimum cosine similarity for a semantic hit (default 0.75).
        """
        t0 = time.monotonic()
        trace_id = str(uuid.uuid4())[:8]

        effective_top_k = top_k if top_k is not None else config.default_top_k
        effective_min_rel = min_relevance if min_relevance is not None else config.min_relevance

        # --- Load knowledge (cached) ---
        rules = get_knowledge(config.knowledge_dir)
        aliases = load_aliases(config.knowledge_dir)

        # --- Pipeline ---
        # 1. Prune nominal observations (no-op when observations list is empty)
        pruned_obs = prune(observations) if observations else []

        # 2. Normalise observation IDs via taxonomy aliases
        normalised_obs = normalize(pruned_obs, aliases)
        obs_ids = {o["observation_id"] for o in normalised_obs}

        # 3. Normalise keywords to lowercase for case-insensitive matching
        kw_set = {k.lower() for k in keywords} if keywords else set()

        # 4. Build semantic query text when Stage 2 is requested (opt-in)
        effective_semantic_query: str | None = None
        effective_index_dir: Any | None = None
        if semantic_search:
            nl_parts: list[str] = []
            if keywords:
                nl_parts.extend(keywords)
            for obs in (observations or []):
                nl_parts.append(str(obs.get("observation_id", "")))
                nl_parts.append(str(obs.get("value", "")))
            if nl_parts:
                effective_semantic_query = " ".join(nl_parts)
            effective_index_dir = str(config.knowledge_dir / ".semantic_index")

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

        # 6. Rank, compress to top_k, strip metadata
        lean_rules = compress(
            candidates,
            obs_ids,
            top_k=effective_top_k,
            min_relevance=effective_min_rel,
        )

        # 7. Render rules as #Rule N: formatted text for direct LLM injection
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        if lean_rules:
            summary = _render_rules_as_text(lean_rules)
            status = "ok"
        else:
            summary = "No domain rules matched the current observations or keywords."
            status = "partial"

        return {
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
                "semantic_search": semantic_search,
                "applied_policies": (
                    ["zero_value_pruning", "lean_context_injection", "semantic_retrieval"]
                    if semantic_search
                    else ["zero_value_pruning", "lean_context_injection"]
                ),
                "trace_id": trace_id,
            },
        }
