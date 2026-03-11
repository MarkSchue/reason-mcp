"""Candidate Rule Filter — semantic retrieval + graph traversal.

Two retrieval paths run for every call:

  Semantic (always active)
      Vector cosine similarity via the vector index on the rules collection.
      Returns each matching rule together with the actual *cosine score*.

  Graph traversal (praxis domain)
      Semantic search over the praxis graph nodes, followed by a 1-hop
      OUTBOUND traversal to collect connected nodes (e.g. WorkingHours linked
      via "arbeitet" edges).  Results are shaped into rule-like dicts so the
      compressor can rank them alongside regular rules.

Catch-all rules (no trigger criteria at all) are always included regardless
of the semantic search result.  This ensures baseline coverage.

Each returned rule has one transient score field attached:
    ``_sem_score``   — 0..1, from the semantic path (0 = catch-all, not in index)

This field is stripped by the compressor before LLM injection.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_key(rule: dict[str, Any]) -> str:
    """Stable composite key: '<domain>::<rule_id>'.  Unique across all files."""
    return f"{rule.get('domain', '')}::{rule.get('rule_id', '')}"


# ---------------------------------------------------------------------------
# Semantic path (rules collection)
# ---------------------------------------------------------------------------

def _sem_candidates(
    rules: list[dict[str, Any]],
    semantic_query: str,
    min_score: float,
    domain: str | None,
) -> list[tuple[dict[str, Any], float]]:
    """Return (rule, cosine_score) pairs for rules found via vector similarity."""
    try:
        from reason_mcp.tools.reasoning.embedder import search_rules as _search
    except ImportError:
        logger.warning("semantic extras not installed — semantic path disabled")
        return []

    rule_by_id: dict[str, dict[str, Any]] = {r.get("rule_id"): r for r in rules}
    try:
        hits: list[tuple[str, float]] = _search(
            semantic_query,
            top_k=len(rules),
            min_score=min_score,
            domain=domain,
        )
    except Exception:
        logger.exception("semantic search failed — semantic path returning empty")
        return []

    return [(rule_by_id[rid], score) for rid, score in hits if rid in rule_by_id]


# ---------------------------------------------------------------------------
# Graph traversal path (praxis nodes collection)
# ---------------------------------------------------------------------------

def _graph_candidates(
    semantic_query: str,
    min_score: float,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search praxis graph nodes semantically, then traverse 1 hop outbound.

    Each matching Worker node is combined with its connected WorkingHours
    (via ``arbeitet`` edges) into a rule-like dict the compressor can rank.

    Returns:
        List of rule-shaped dicts with ``_sem_score`` and ``_source="graph"``
        attached.  Empty on any DB or embedding failure.
    """
    try:
        from reason_mcp.tools.reasoning.embedder import embed_text
        from reason_mcp.knowledge.arango_client import (
            vector_search_nodes,
            traverse_from_node,
        )
    except ImportError:
        logger.warning("graph traversal dependencies not available")
        return []

    try:
        query_embedding = embed_text(semantic_query)
        node_hits = vector_search_nodes(
            query_embedding, top_k=top_k, min_score=min_score
        )
    except Exception:
        logger.exception("praxis node search failed")
        return []

    candidates: list[dict[str, Any]] = []

    for node_id, score in node_hits:
        # Traverse 1 hop outbound to get connected WorkingHours nodes
        try:
            steps = traverse_from_node(node_id, depth=1, direction="OUTBOUND")
        except Exception:
            logger.warning("graph traversal failed for node", node_id=node_id)
            steps = []

        # Build a natural-language description from the traversal subgraph
        connected_descriptions: list[str] = []
        for step in steps:
            vertex = step.get("vertex", {})
            edge = step.get("edge", {})
            edge_label = edge.get("label", edge.get("type", ""))
            vertex_desc = vertex.get("description", vertex.get("name", ""))
            if edge_label or vertex_desc:
                connected_descriptions.append(
                    f"{edge_label}: {vertex_desc}" if edge_label else vertex_desc
                )

        # Compose a rule-shaped dict from the graph node + neighbours
        # (must have conditions.natural_language for the renderer to work)
        # Start from the matched node's own description and append neighbours
        start_node_desc = f"(node {node_id} description unavailable)"
        try:
            # Pull the full node doc for the description
            from reason_mcp.knowledge.arango_client import get_graph_db, _vertex_coll_for_node_id
            db = get_graph_db()
            doc = db.collection(_vertex_coll_for_node_id(node_id)).get(node_id)
            if doc:
                start_node_desc = doc.get("description", doc.get("name", start_node_desc))
        except Exception:
            pass

        nl = start_node_desc
        if connected_descriptions:
            nl += "\n" + " | ".join(connected_descriptions)

        candidate: dict[str, Any] = {
            "rule_id": node_id,
            "domain": "praxis",
            "conditions": {"natural_language": nl},
            "reasoning": {
                "possible_causes": connected_descriptions or [start_node_desc],
                "confidence_prior": 0.9,
            },
            "recommendation": {
                "action": (
                    f"Kontaktieren Sie {doc.get('name', node_id)} innerhalb der angegebenen Arbeitszeiten."
                    if doc else f"Kontaktieren Sie {node_id} innerhalb der angegebenen Arbeitszeiten."
                ),
            },
            "scoring": {"severity": 2, "specificity": 0.9},
            "_sem_score": score,
            "_source": "graph",
        }
        candidates.append(candidate)

    logger.info(
        "graph_filter",
        query=semantic_query[:60],
        node_hits=len(node_hits),
        candidates=len(candidates),
    )
    return candidates


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def filter_candidates(
    rules: list[dict[str, Any]],
    domain: str | None = None,
    semantic_query: str | None = None,
    semantic_min_score: float = 0.45,
) -> list[dict[str, Any]]:
    """Return candidate rules from semantic retrieval, graph traversal, and catch-all rules.

    Three sources are merged:
    1. Semantic hits from the rules collection (vector similarity).
    2. Graph traversal hits from the praxis nodes collection (if a query is given).
    3. Catch-all rules (no trigger criteria) — always included.

    Each returned dict has ``_sem_score`` attached for downstream ranking.

    Args:
        rules: Full rule list from the knowledge store.
        domain: Optional domain hint — rules with a different domain are excluded.
        semantic_query: NL text to embed and search against.  When omitted, only
            catch-all rules and any graph results are returned.
        semantic_min_score: Minimum cosine similarity for a semantic hit.
    """
    # --- Semantic path (rules DB) ---
    sem_by_key: dict[str, tuple[dict[str, Any], float]] = {}
    if semantic_query:
        sem_results = _sem_candidates(rules, semantic_query, semantic_min_score, domain)
        sem_by_key = {_rule_key(r): (r, score) for r, score in sem_results}

    # --- Graph traversal path (praxis nodes) ---
    graph_results: list[dict[str, Any]] = []
    if semantic_query:
        graph_results = _graph_candidates(semantic_query, semantic_min_score)

    # --- Catch-all rules (domain-filtered, always included) ---
    catch_all_by_key: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if domain and rule.get("domain") and rule["domain"] != domain:
            continue
        trigger = rule.get("trigger", {})
        has_criteria = (
            bool(trigger.get("observations"))
            or bool(trigger.get("keywords"))
            or bool(trigger.get("context_states"))
        )
        if not has_criteria:
            catch_all_by_key[_rule_key(rule)] = rule

    # --- Merge: semantic rules + graph nodes + catch-all ---
    all_rule_keys: set[str] = set(sem_by_key) | set(catch_all_by_key)
    candidates: list[dict[str, Any]] = []

    for key in all_rule_keys:
        if key in sem_by_key:
            rule, sem_score = sem_by_key[key]
        else:
            rule = catch_all_by_key[key]
            sem_score = 0.0
        rule["_sem_score"] = sem_score
        candidates.append(rule)

    # Graph results are appended directly (already have _sem_score from node search)
    candidates.extend(graph_results)

    logger.info(
        "candidate filter",
        total_rules=len(rules),
        sem_hits=len(sem_by_key),
        catch_all_hits=len(catch_all_by_key),
        graph_hits=len(graph_results),
        candidates=len(candidates),
        domain=domain,
    )
    return candidates
