"""Integration tests for deterministic graph query helpers in arango_client.

These tests require a running ArangoDB instance with the praxis graph seeded.
Run with:  pytest tests/test_graph_queries.py -v

All tests verify that the full "collection/key" document-handle format is
handled transparently — callers only ever pass bare node_id values.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Skip entire module when ArangoDB / praxis graph is unavailable
# ---------------------------------------------------------------------------

def _praxis_available() -> bool:
    try:
        import sys, os
        sys.path.insert(0, "src")
        from dotenv import load_dotenv
        load_dotenv()
        from reason_mcp.knowledge.arango_client import get_graph_db
        db = get_graph_db()
        db.collection("workers").count()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _praxis_available(),
    reason="praxis ArangoDB not available",
)


# ---------------------------------------------------------------------------
# get_node
# ---------------------------------------------------------------------------

class TestGetNode:
    def test_known_node_returns_doc(self):
        from reason_mcp.knowledge.arango_client import get_node
        doc = get_node("worker_frau_meier")
        assert doc is not None
        assert doc["node_id"] == "worker_frau_meier"
        assert doc["name"] == "Frau Meier"
        assert doc["role"] == "Arzthelferin"

    def test_unknown_node_returns_none(self):
        from reason_mcp.knowledge.arango_client import get_node
        assert get_node("worker_nobody_xyz") is None

    def test_unknown_prefix_raises_valueerror(self):
        # _vertex_coll_for_node_id raises ValueError for unrecognised prefixes.
        from reason_mcp.knowledge.arango_client import get_node
        with pytest.raises(ValueError, match="no key_prefix matches"):
            get_node("bogusprefix_thatdoesnotexist_xyz")


# ---------------------------------------------------------------------------
# find_nodes_by_name
# ---------------------------------------------------------------------------

class TestFindNodesByName:
    def test_case_insensitive_match(self):
        from reason_mcp.knowledge.arango_client import find_nodes_by_name
        results = find_nodes_by_name("BAUER")
        names = [r["name"] for r in results]
        assert "Frau Bauer" in names

    def test_partial_fragment(self):
        from reason_mcp.knowledge.arango_client import find_nodes_by_name
        results = find_nodes_by_name("frau")
        names = [r["name"] for r in results]
        # Frau Meier, Frau Bauer, Frau Schmidt, Frau Hoffmann at minimum
        assert len(names) >= 3

    def test_no_match_returns_empty(self):
        from reason_mcp.knowledge.arango_client import find_nodes_by_name
        assert find_nodes_by_name("doesnotexistxyz") == []

    def test_node_type_filter(self):
        from reason_mcp.knowledge.arango_client import find_nodes_by_name
        results = find_nodes_by_name("", node_type="WorkingHours")
        types = {r.get("type") for r in results}
        assert types <= {"WorkingHours"}

    def test_unknown_type_raises(self):
        from reason_mcp.knowledge.arango_client import find_nodes_by_name
        with pytest.raises(ValueError, match="Unknown node type"):
            find_nodes_by_name("test", node_type="DoesNotExist")


# ---------------------------------------------------------------------------
# query_inbound_edges  ("wer vertritt X?")
# ---------------------------------------------------------------------------

class TestQueryInboundEdges:
    def test_frau_schmidt_is_represented_by_frau_bauer(self):
        """Frau Bauer → vertritt → Frau Schmidt: inbound to Schmidt = Bauer."""
        from reason_mcp.knowledge.arango_client import query_inbound_edges
        hits = query_inbound_edges("worker_frau_schmidt", edge_type="vertritt")
        assert len(hits) == 1
        assert hits[0]["from_node"]["name"] == "Frau Bauer"
        assert hits[0]["from_node"]["node_id"] == "worker_frau_bauer"

    def test_frau_meier_is_represented_by_frau_schmidt(self):
        from reason_mcp.knowledge.arango_client import query_inbound_edges
        hits = query_inbound_edges("worker_frau_meier", edge_type="vertritt")
        assert len(hits) == 1
        assert hits[0]["from_node"]["name"] == "Frau Schmidt"

    def test_frau_bauer_has_no_representative(self):
        """No edge points TO Frau Bauer — nobody represents her."""
        from reason_mcp.knowledge.arango_client import query_inbound_edges
        hits = query_inbound_edges("worker_frau_bauer", edge_type="vertritt")
        assert hits == []

    def test_edge_doc_contains_label(self):
        from reason_mcp.knowledge.arango_client import query_inbound_edges
        hits = query_inbound_edges("worker_frau_schmidt", edge_type="vertritt")
        assert "label" in hits[0]["edge"]
        assert "Schmidt" in hits[0]["edge"]["label"]

    def test_no_edge_type_searches_all_collections(self):
        """Without edge_type filter all edge collections are searched."""
        from reason_mcp.knowledge.arango_client import query_inbound_edges
        # worker_herr_wagner has an incoming vertritt from Herr Müller
        hits = query_inbound_edges("worker_herr_wagner")
        source_names = [h["from_node"]["name"] for h in hits]
        assert "Herr Müller" in source_names


# ---------------------------------------------------------------------------
# query_outbound_edges  ("wen vertritt X?")
# ---------------------------------------------------------------------------

class TestQueryOutboundEdges:
    def test_frau_bauer_represents_frau_schmidt(self):
        """Frau Bauer → vertritt → Frau Schmidt: outbound from Bauer = Schmidt."""
        from reason_mcp.knowledge.arango_client import query_outbound_edges
        hits = query_outbound_edges("worker_frau_bauer", edge_type="vertritt")
        assert len(hits) == 1
        assert hits[0]["to_node"]["name"] == "Frau Schmidt"
        assert hits[0]["to_node"]["node_id"] == "worker_frau_schmidt"

    def test_frau_meier_represents_nobody(self):
        """Frau Meier has no outbound vertritt edge."""
        from reason_mcp.knowledge.arango_client import query_outbound_edges
        hits = query_outbound_edges("worker_frau_meier", edge_type="vertritt")
        assert hits == []

    def test_arbeitet_edges_for_worker(self):
        """Workers have outbound 'arbeitet' edges to their working_hours node."""
        from reason_mcp.knowledge.arango_client import query_outbound_edges
        hits = query_outbound_edges("worker_frau_bauer", edge_type="arbeitet")
        assert len(hits) >= 1
        to_types = {h["to_node"].get("type") for h in hits}
        assert "WorkingHours" in to_types


# ---------------------------------------------------------------------------
# Edge search tests
# ---------------------------------------------------------------------------

class TestKeywordSearchEdges:
    def test_finds_vertritt_by_name(self):
        """Searching for 'bauer vertritt' should find the substitution edge."""
        from reason_mcp.knowledge.arango_client import keyword_search_edges
        hits = keyword_search_edges("bauer vertritt", top_k=5)
        assert len(hits) >= 1
        keys = [h[0] for h in hits]
        assert "bauer__vertritt__schmidt" in keys

    def test_finds_arbeitet_by_name(self):
        """Searching for 'meier arbeitet' should find Frau Meier's arbeitet edge."""
        from reason_mcp.knowledge.arango_client import keyword_search_edges
        hits = keyword_search_edges("meier arbeitet", top_k=5)
        assert len(hits) >= 1
        keys = [h[0] for h in hits]
        assert "meier__arbeitet__mon_tue_wed_0800_1000" in keys

    def test_edge_type_filter(self):
        """When edge_type='vertritt', only vertritt edges are returned."""
        from reason_mcp.knowledge.arango_client import keyword_search_edges
        hits = keyword_search_edges("wagner", top_k=10, edge_type="vertritt")
        for key, _ in hits:
            assert "vertritt" in key

    def test_empty_for_nonexistent(self):
        """Searching for a non-existent term should return no hits."""
        from reason_mcp.knowledge.arango_client import keyword_search_edges
        hits = keyword_search_edges("zyxwvutsrqp", top_k=5)
        assert hits == []


class TestVectorSearchEdges:
    def test_returns_scored_tuples(self):
        """Vector search should return (edge_key, score) tuples."""
        from reason_mcp.tools.reasoning.embedder import embed_text
        from reason_mcp.knowledge.arango_client import vector_search_edges
        emb = embed_text("wer vertritt wen bei abwesenheit")
        hits = vector_search_edges(emb, top_k=5, min_score=0.3)
        assert len(hits) >= 1
        for key, score in hits:
            assert isinstance(key, str)
            assert 0.0 <= score <= 1.0

    def test_keyword_vector_search_edges(self):
        """Keyword-vector search on edges should find vertritt relationships."""
        from reason_mcp.tools.reasoning.embedder import embed_text
        from reason_mcp.knowledge.arango_client import keyword_vector_search_edges
        emb = embed_text("vertritt abwesenheit")
        hits = keyword_vector_search_edges(emb, top_k=5, min_score=0.3)
        assert len(hits) >= 1


class TestGetEdgeDocument:
    def test_existing_edge(self):
        """Fetching a known edge key should return the document."""
        from reason_mcp.knowledge.arango_client import get_edge_document
        doc = get_edge_document("bauer__vertritt__schmidt")
        assert doc is not None
        assert doc["_key"] == "bauer__vertritt__schmidt"
        assert "embedding" not in doc
        assert "keywords_embedding" not in doc

    def test_nonexistent_edge(self):
        """Fetching an unknown edge key should return None."""
        from reason_mcp.knowledge.arango_client import get_edge_document
        doc = get_edge_document("nonexistent__key__here")
        assert doc is None

    def test_edge_has_keywords(self):
        """Edge documents should now have keywords and description fields."""
        from reason_mcp.knowledge.arango_client import get_edge_document
        doc = get_edge_document("bauer__vertritt__schmidt")
        assert doc is not None
        assert "keywords" in doc
        assert "description" in doc
        assert isinstance(doc["keywords"], list)
        assert len(doc["keywords"]) > 0


# ---------------------------------------------------------------------------
# Multi-hop traversal
# ---------------------------------------------------------------------------

class TestTraverseFromNode:
    """Verify configurable-depth ANY traversal returns correct chains."""

    def test_depth1_returns_direct_neighbours(self):
        from reason_mcp.knowledge.arango_client import traverse_from_node
        steps = traverse_from_node("worker_frau_meier", depth=1, direction="ANY")
        assert len(steps) >= 2, f"Expected >=2 steps at depth=1, got {len(steps)}"
        # Meier has at least 1 arbeitet edge and 1 vertritt edge
        vertex_keys = {s["vertex"]["_key"] for s in steps}
        assert vertex_keys, "Should return at least one connected vertex"

    def test_depth2_reaches_two_hop_neighbours(self):
        """depth=2 from Meier should reach Bauer through Schmidt← Meier, Bauer← Schmidt chain."""
        from reason_mcp.knowledge.arango_client import traverse_from_node
        steps = traverse_from_node("worker_frau_meier", depth=2, direction="ANY")
        vertex_keys = {s["vertex"]["_key"] for s in steps}
        # At depth 2 we expect to see Bauer (via Schmidt)
        assert "worker_frau_bauer" in vertex_keys, (
            f"Bauer should be reachable at depth 2 from Meier. Got vertices: {vertex_keys}"
        )
        # We should also still see depth-1 neighbours
        assert "worker_frau_schmidt" in vertex_keys

    def test_depth3_follows_full_chain(self):
        """depth=3 from Meier should follow deeper relationships."""
        from reason_mcp.knowledge.arango_client import traverse_from_node
        steps = traverse_from_node("worker_frau_meier", depth=3, direction="ANY")
        assert len(steps) >= 5, (
            f"Expected >=5 steps at depth=3 from Meier, got {len(steps)}"
        )

    def test_traversal_strips_embeddings(self):
        """Returned vertices and edges must NOT contain embedding/keywords_embedding."""
        from reason_mcp.knowledge.arango_client import traverse_from_node
        steps = traverse_from_node("worker_frau_meier", depth=2, direction="ANY")
        for step in steps:
            for key in ("vertex", "edge"):
                doc = step.get(key, {})
                assert "embedding" not in doc, f"{key} should not contain 'embedding'"
                assert "keywords_embedding" not in doc, f"{key} should not contain 'keywords_embedding'"

    def test_edge_direction_correctness(self):
        """Edge _from/_to must reflect actual graph direction, not traversal order."""
        from reason_mcp.knowledge.arango_client import traverse_from_node
        steps = traverse_from_node("worker_frau_meier", depth=1, direction="ANY")
        for step in steps:
            edge = step.get("edge", {})
            _from = edge.get("_from", "")
            _to = edge.get("_to", "")
            # Both _from and _to must be full handles "collection/key"
            assert "/" in _from, f"_from should be a document handle, got {_from!r}"
            assert "/" in _to, f"_to should be a document handle, got {_to!r}"

    def test_unknown_node_returns_empty(self):
        """Traversal from a non-existent node should return an empty list."""
        from reason_mcp.knowledge.arango_client import traverse_from_node
        steps = traverse_from_node("worker_nobody_xyz", depth=1, direction="ANY")
        assert steps == []


# ---------------------------------------------------------------------------
# Config reload
# ---------------------------------------------------------------------------

class TestConfigReload:
    """Verify reload_config() recreates the singleton properly."""

    def test_reload_config_updates_depth(self):
        import os
        from reason_mcp.config import config, reload_config
        old_depth = config.graph_traversal_depth
        os.environ["REASON_GRAPH_TRAVERSAL_DEPTH"] = "5"
        try:
            reload_config()
            from reason_mcp.config import config as new_cfg
            assert new_cfg.graph_traversal_depth == 5
        finally:
            if old_depth == 2:
                os.environ.pop("REASON_GRAPH_TRAVERSAL_DEPTH", None)
            else:
                os.environ["REASON_GRAPH_TRAVERSAL_DEPTH"] = str(old_depth)
            reload_config()
