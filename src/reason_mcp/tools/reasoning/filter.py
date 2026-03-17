"""Candidate Rule Filter — semantic retrieval + graph traversal.

Three retrieval paths run for every call:

  Semantic (always active)
      Vector cosine similarity via the vector index on the rules collection.
      Returns each matching rule together with the actual *cosine score*.

  Graph node search + traversal
      Semantic + keyword search over the graph vertex collections, followed
      by a configurable-depth ANY traversal (env ``REASON_GRAPH_TRAVERSAL_DEPTH``,
      default 2) to collect connected nodes and edges.  Both inbound and
      outbound edges are captured with explicit direction markers.

  Graph edge search
      Semantic + keyword search directly over edge collections.  Catches
      queries that match relationship labels/descriptions even when the
      endpoint nodes do not score high enough on their own.

Catch-all rules (no trigger criteria at all) are always included regardless
of the semantic search result.  This ensures baseline coverage.

All collection names, edge topologies, and domain labels are config-driven
via ``REASON_PRAXIS_VERTEX_SPECS`` and ``REASON_PRAXIS_EDGE_SPECS`` — no
domain-specific knowledge is hardcoded in this module.

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

def _graph_domain() -> str:
    """Return the graph database name used as domain label for graph candidates.

    Reads from :attr:`~reason_mcp.config.Config.praxis_db` so the value
    tracks whatever database the deployment is configured with.
    """
    try:
        from reason_mcp.config import config
        return config.praxis_db
    except Exception:
        return "graph"


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
    """Search praxis graph nodes AND edges semantically, then traverse to build context.

    Two parallel retrieval strategies:

    **Node-first** (existing):
        Semantic + keyword search over vertex collections, then 1-hop ANY
        traversal to collect connected nodes and edges.

    **Edge-first** (new):
        Semantic + keyword search directly over edge collections, then resolve
        the endpoint nodes for full context.  This catches queries that match
        edge labels/relationships even when the involved nodes don't score
        high enough on their own.

    Both sets of candidates are merged (deduped by ``rule_id``).

    Returns:
        List of rule-shaped dicts with ``_sem_score`` and ``_source="graph"``
        attached.  Empty on any DB or embedding failure.
    """
    try:
        from reason_mcp.tools.reasoning.embedder import embed_text
        from reason_mcp.knowledge.arango_client import (
            vector_search_nodes,
            keyword_search_nodes,
            keyword_vector_search_nodes,
            vector_search_edges,
            keyword_search_edges,
            keyword_vector_search_edges,
            get_edge_document,
            traverse_from_node,
            get_graph_db,
            _vertex_coll_for_node_id,
        )
    except ImportError:
        logger.warning("graph traversal dependencies not available")
        return []

    # --- Embed query once ---
    query_embedding: list[float] | None = None
    try:
        query_embedding = embed_text(semantic_query)
    except Exception:
        logger.exception("failed to embed query for graph search")

    # ─── NODE-FIRST PATH ─────────────────────────────────────────────
    # Semantic vector search (description embedding)
    sem_hits: list[tuple[str, float]] = []
    if query_embedding:
        try:
            sem_hits = vector_search_nodes(
                query_embedding, top_k=top_k, min_score=min_score
            )
        except Exception:
            logger.exception("praxis semantic node search failed")

    # Keyword vector search (keywords_embedding)
    kw_vec_hits: list[tuple[str, float]] = []
    if query_embedding:
        try:
            kw_vec_hits = keyword_vector_search_nodes(
                query_embedding, top_k=top_k, min_score=min_score
            )
        except Exception:
            logger.exception("praxis keyword vector search failed")

    # AQL keyword / name search (no embedding required)
    kw_hits: list[tuple[str, float]] = []
    try:
        kw_hits = keyword_search_nodes(semantic_query, top_k=top_k)
    except Exception:
        logger.exception("praxis keyword node search failed")

    # Merge all three node paths: highest score per node_id, trim to top_k
    best_nodes: dict[str, float] = {}
    for node_id, score in sem_hits + kw_vec_hits + kw_hits:
        if node_id not in best_nodes or score > best_nodes[node_id]:
            best_nodes[node_id] = score
    node_hits: list[tuple[str, float]] = sorted(
        best_nodes.items(), key=lambda x: x[1], reverse=True
    )[:top_k]

    # ─── EDGE-FIRST PATH ─────────────────────────────────────────────
    edge_sem_hits: list[tuple[str, float]] = []
    if query_embedding:
        try:
            edge_sem_hits = vector_search_edges(
                query_embedding, top_k=top_k, min_score=min_score
            )
        except Exception:
            logger.exception("praxis semantic edge search failed")

    edge_kw_vec_hits: list[tuple[str, float]] = []
    if query_embedding:
        try:
            edge_kw_vec_hits = keyword_vector_search_edges(
                query_embedding, top_k=top_k, min_score=min_score
            )
        except Exception:
            logger.exception("praxis keyword vector edge search failed")

    edge_kw_hits: list[tuple[str, float]] = []
    try:
        edge_kw_hits = keyword_search_edges(semantic_query, top_k=top_k)
    except Exception:
        logger.exception("praxis keyword edge search failed")

    best_edges: dict[str, float] = {}
    for edge_key, score in edge_sem_hits + edge_kw_vec_hits + edge_kw_hits:
        if edge_key not in best_edges or score > best_edges[edge_key]:
            best_edges[edge_key] = score
    edge_hits: list[tuple[str, float]] = sorted(
        best_edges.items(), key=lambda x: x[1], reverse=True
    )[:top_k]

    if not node_hits and not edge_hits:
        return []

    candidates: list[dict[str, Any]] = []
    seen_rule_ids: set[str] = set()

    # ─── Build candidates from NODE hits + traversal ──────────────────
    from reason_mcp.config import config as _cfg

    _traversal_depth = _cfg.graph_traversal_depth

    for node_id, score in node_hits:
        try:
            steps = traverse_from_node(node_id, depth=_traversal_depth, direction="ANY")
        except Exception:
            logger.warning("graph traversal failed for node", node_id=node_id)
            steps = []

        connected_descriptions: list[str] = []
        for step in steps:
            vertex = step.get("vertex", {})
            edge = step.get("edge", {})
            edge_label = edge.get("label", edge.get("description", edge.get("type", "")))
            vertex_desc = vertex.get("description", vertex.get("name", ""))

            # Derive actual edge direction from _from/_to document handles.
            edge_from_key = (edge.get("_from") or "").split("/")[-1]
            edge_to_key = (edge.get("_to") or "").split("/")[-1]
            vertex_key = vertex.get("_key", "")

            # Show the relationship as: source → label → target
            # The traversed-to vertex is `vertex`; the other end is the peer.
            if vertex_key == edge_to_key:
                # outbound edge: peer → vertex
                desc = f"{edge_from_key} →{edge_label}→ {vertex_desc}" if edge_label else f"{edge_from_key} → {vertex_desc}"
            else:
                # inbound edge: vertex → peer
                desc = f"{vertex_desc} →{edge_label}→ {edge_to_key}" if edge_label else f"{vertex_desc} → {edge_to_key}"

            if edge_label or vertex_desc:
                connected_descriptions.append(desc)

        start_node_desc = f"(node {node_id} description unavailable)"
        doc = None
        try:
            db = get_graph_db()
            doc = db.collection(_vertex_coll_for_node_id(node_id)).get(node_id)
            if doc:
                start_node_desc = doc.get("description", doc.get("name", start_node_desc))
        except Exception:
            pass

        nl = start_node_desc
        if connected_descriptions:
            nl += "\n" + " | ".join(connected_descriptions)

        rule_id = node_id
        seen_rule_ids.add(rule_id)
        node_name = doc.get("name", node_id) if doc else node_id
        candidate: dict[str, Any] = {
            "rule_id": rule_id,
            "domain": _graph_domain(),
            "conditions": {"natural_language": nl},
            "reasoning": {
                "possible_causes": connected_descriptions or [start_node_desc],
                "confidence_prior": 0.9,
            },
            "recommendation": {
                "action": f"See node {node_name} and its connected relationships.",
            },
            "scoring": {"severity": 2, "specificity": 0.9},
            "_sem_score": score,
            "_source": "graph",
        }
        candidates.append(candidate)

    # ─── Build candidates from EDGE hits ──────────────────────────────
    for edge_key, score in edge_hits:
        edge_doc = None
        try:
            edge_doc = get_edge_document(edge_key)
        except Exception:
            logger.warning("failed to fetch edge document", edge_key=edge_key)
            continue

        if not edge_doc:
            continue

        # Resolve endpoint nodes
        from_key = (edge_doc.get("_from") or "").split("/")[-1]
        to_key = (edge_doc.get("_to") or "").split("/")[-1]

        # Skip if we already created a candidate covering the same nodes
        # (the node-first path would have traversed through this edge)
        if from_key in seen_rule_ids and to_key in seen_rule_ids:
            continue

        edge_desc = edge_doc.get("description", edge_doc.get("label", edge_doc.get("type", "")))

        # Resolve endpoint names
        from_name = from_key
        to_name = to_key
        try:
            db = get_graph_db()
            from_coll = (edge_doc.get("_from") or "").split("/")[0]
            to_coll = (edge_doc.get("_to") or "").split("/")[0]
            from_node = db.collection(from_coll).get(from_key) if from_coll else None
            to_node = db.collection(to_coll).get(to_key) if to_coll else None
            if from_node:
                from_name = from_node.get("name", from_key)
            if to_node:
                to_name = to_node.get("name", to_key)
        except Exception:
            pass

        nl = f"{edge_desc}\n→ {from_name} → {to_name}"

        rule_id = f"edge:{edge_key}"
        seen_rule_ids.add(rule_id)
        candidate = {
            "rule_id": rule_id,
            "domain": _graph_domain(),
            "conditions": {"natural_language": nl},
            "reasoning": {
                "possible_causes": [edge_desc],
                "confidence_prior": 0.85,
            },
            "recommendation": {
                "action": f"Relationship: {from_name} → {to_name} ({edge_doc.get('type', '')})",
            },
            "scoring": {"severity": 2, "specificity": 0.85},
            "_sem_score": score,
            "_source": "graph_edge",
        }
        candidates.append(candidate)

    logger.info(
        "graph_filter",
        query=semantic_query[:60],
        node_hits=len(node_hits),
        edge_hits=len(edge_hits),
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

    Four sources are merged:
    1. Semantic hits from the rules collection (vector similarity).
    2. Graph node search + traversal hits from vertex collections (if a query is given).
    3. Graph edge search hits from edge collections (if a query is given).
    4. Catch-all rules (no trigger criteria) — always included.

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

    # --- Graph path (node + edge search, traversal) ---
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
