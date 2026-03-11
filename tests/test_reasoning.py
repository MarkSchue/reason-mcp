"""Tests for the reasoning pipeline stages."""

from __future__ import annotations

import pytest

from reason_mcp.tools.reasoning.pruner import prune
from reason_mcp.tools.reasoning.normalizer import normalize
from reason_mcp.tools.reasoning.filter import filter_candidates
from reason_mcp.tools.reasoning.compressor import compress
from reason_mcp.tools.reasoning.tool import _render_rules_as_text


# ---------------------------------------------------------------------------
# Pruner
# ---------------------------------------------------------------------------


def test_prune_keeps_anomalies_with_explicit_range():
    obs = [
        {"observation_id": "OBS_PRESSURE", "value": 12.0},  # above range → keep
        {"observation_id": "OBS_PRESSURE", "value": 9.0},   # within range → prune
    ]
    result = prune(obs, nominal_ranges={"OBS_PRESSURE": (8.0, 10.0)})
    assert len(result) == 1
    assert result[0]["value"] == 12.0


def test_prune_keeps_all_string_observations():
    obs = [{"observation_id": "OBS_STATE", "value": "ACTIVE"}]
    result = prune(obs)
    assert len(result) == 1


def test_prune_statistical_outlier():
    # First 9 values are nominal (8-10), last one is far outlier
    obs = [{"observation_id": f"OBS_{i}", "value": float(9)} for i in range(9)]
    obs.append({"observation_id": "OBS_SPIKE", "value": 99.0})
    result = prune(obs)
    assert any(o["observation_id"] == "OBS_SPIKE" for o in result)


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


def test_normalize_replaces_alias():
    obs = [{"observation_id": "DP_042", "value": 12.5}]
    result = normalize(obs, aliases={"DP_042": "OBS_PRESSURE"})
    assert result[0]["observation_id"] == "OBS_PRESSURE"


def test_normalize_passthrough_when_no_alias():
    obs = [{"observation_id": "OBS_PRESSURE", "value": 12.5}]
    result = normalize(obs, aliases={})
    assert result[0]["observation_id"] == "OBS_PRESSURE"


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


RULES = [
    {
        "rule_id": "R-001",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {
            "observations": ["OBS_VEHICLE_SEEN"],
            "keywords": ["car", "vehicle", "convertible"],
        },
        "conditions": {"natural_language": "A red car is always a convertible."},
        "reasoning": {"confidence_prior": 0.9},
        "scoring": {"severity": 2},
    },
    {
        "rule_id": "R-002",
        "domain": "industrial",
        "active": True,
        "trigger": {
            "observations": ["OBS_PRESSURE"],
            "context_states": ["PRODUCTION"],
            "keywords": ["pressure", "industrial", "valve"],
        },
        "conditions": {"natural_language": "Pressure out of bounds."},
        "reasoning": {"confidence_prior": 0.85},
        "scoring": {"severity": 4},
    },
    {
        # keyword-only rule: no observations trigger
        "rule_id": "R-003",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {
            "keywords": ["speed", "highway", "overspeed"],
        },
        "conditions": {"natural_language": "Speed must not exceed 120 km/h."},
        "reasoning": {"confidence_prior": 0.95},
        "scoring": {"severity": 5},
    },
]


def test_filter_catch_all_always_returned():
    """A rule with no trigger criteria is always included regardless of query."""
    catch_all = {
        "rule_id": "R-CATCHALL",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {},  # no criteria → catch-all
        "conditions": {"natural_language": "Default guidance."},
        "reasoning": {"confidence_prior": 0.5},
        "scoring": {"severity": 1},
    }
    result = filter_candidates([catch_all], domain="fleet_tracking")
    ids = [r["rule_id"] for r in result]
    assert "R-CATCHALL" in ids


def test_filter_catch_all_returned_without_semantic_query():
    """Catch-all requires no semantic_query to appear in results."""
    catch_all = {
        "rule_id": "R-CATCHALL",
        "domain": None,
        "active": True,
        "trigger": {},
        "conditions": {"natural_language": "No criteria."},
        "reasoning": {"confidence_prior": 0.5},
        "scoring": {"severity": 1},
    }
    result = filter_candidates([catch_all])
    assert len(result) == 1
    assert result[0]["rule_id"] == "R-CATCHALL"
    assert result[0]["_sem_score"] == 0.0


def test_filter_domain_excludes_non_matching_domain():
    """Rules from a different domain are excluded even if they are catch-all."""
    other_domain = {
        "rule_id": "R-OTHER",
        "domain": "industrial",
        "active": True,
        "trigger": {},
        "conditions": {"natural_language": "Industrial default."},
        "reasoning": {"confidence_prior": 0.5},
        "scoring": {"severity": 1},
    }
    result = filter_candidates([other_domain], domain="fleet_tracking")
    assert result == []


def test_filter_no_domain_includes_all_catch_all():
    """When no domain is specified, catch-all rules of any domain are included."""
    r1 = {**RULES[0], "rule_id": "R-CA1", "trigger": {}}
    r2 = {**RULES[1], "rule_id": "R-CA2", "trigger": {}}
    result = filter_candidates([r1, r2], domain=None)
    ids = [r["rule_id"] for r in result]
    assert "R-CA1" in ids
    assert "R-CA2" in ids


def test_filter_semantic_query_adds_candidates(monkeypatch):
    """Rules found only by semantic search are included in the candidate set."""
    sem_rule = {
        "rule_id": "R-SEM-001",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {"keywords": ["unreachable"]},  # won't be triggered by filter
        "conditions": {"natural_language": "Condition for R-SEM-001."},
        "reasoning": {"confidence_prior": 0.8},
        "scoring": {"severity": 3},
    }

    def fake_search(query, top_k, min_score, domain):
        return [("R-SEM-001", 0.82)]

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    result = filter_candidates(
        [sem_rule],
        domain="fleet_tracking",
        semantic_query="some query text",
        semantic_min_score=0.75,
    )
    ids = [r["rule_id"] for r in result]
    assert "R-SEM-001" in ids
    match = next(r for r in result if r["rule_id"] == "R-SEM-001")
    assert match["_sem_score"] == 0.82


def test_filter_semantic_query_off_by_default():
    """Without a semantic_query, only catch-all rules are returned."""
    catch_all = {
        "rule_id": "R-SEM-002",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {},
        "conditions": {"natural_language": "Default rule."},
        "reasoning": {"confidence_prior": 0.8},
        "scoring": {"severity": 3},
    }
    result = filter_candidates(
        [catch_all],
        domain="fleet_tracking",
    )
    ids = [r["rule_id"] for r in result]
    assert "R-SEM-002" in ids


def test_filter_semantic_and_catch_all_union(monkeypatch):
    """Semantic hit and catch-all rule are both present in the result set."""
    catch_all = {
        "rule_id": "R-CATCHALL",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {},
        "conditions": {"natural_language": "Default."},
        "reasoning": {"confidence_prior": 0.5},
        "scoring": {"severity": 1},
    }
    targeted = {
        "rule_id": "R-TARGET",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {"keywords": ["something"]},
        "conditions": {"natural_language": "Targeted rule."},
        "reasoning": {"confidence_prior": 0.8},
        "scoring": {"severity": 3},
    }

    def fake_search(query, top_k, min_score, domain):
        return [("R-TARGET", 0.91)]

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    result = filter_candidates(
        [catch_all, targeted],
        domain="fleet_tracking",
        semantic_query="targeted query",
        semantic_min_score=0.75,
    )
    ids = [r["rule_id"] for r in result]
    assert "R-TARGET" in ids
    assert "R-CATCHALL" in ids
    t = next(r for r in result if r["rule_id"] == "R-TARGET")
    assert t["_sem_score"] == 0.91
    c = next(r for r in result if r["rule_id"] == "R-CATCHALL")
    assert c["_sem_score"] == 0.0


def test_filter_semantic_finds_rule_with_unmatched_keyword_trigger(monkeypatch):
    """Core use case: rule has keyword trigger that does NOT match query text.
    Semantic search finds it anyway; rule must appear with sem_score > 0."""
    mueller_rule = {
        "rule_id": "R-MUELLER",
        "domain": "Praxisbesetzung",
        "active": True,
        "trigger": {"keywords": ["Urlaub", "Krankheit"]},
        "conditions": {"natural_language": "Hr. Müller arbeitet Do und Fr 08-10 Uhr"},
        "reasoning": {"confidence_prior": 0.95},
        "scoring": {"specificity": 0.9},
    }

    def fake_search(query, top_k, min_score, domain):
        return [("R-MUELLER", 0.78)]

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    result = filter_candidates(
        [mueller_rule],
        domain="Praxisbesetzung",
        semantic_query="Hr. Müller montag nicht da",
        semantic_min_score=0.70,
    )
    ids = [r["rule_id"] for r in result]
    assert "R-MUELLER" in ids
    match = next(r for r in result if r["rule_id"] == "R-MUELLER")
    assert match["_sem_score"] == 0.78


def test_filter_catch_all_survives_semantic_failure(monkeypatch):
    """Catch-all rule is still returned even when the semantic path raises."""
    catch_all = {
        "rule_id": "R-CATCHALL",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {},
        "conditions": {"natural_language": "Default guidance."},
        "reasoning": {"confidence_prior": 0.5},
        "scoring": {"severity": 1},
    }

    def fake_search_error(query, top_k, min_score, domain):
        raise RuntimeError("model not available")

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search_error
    )
    result = filter_candidates(
        [catch_all],
        domain="fleet_tracking",
        semantic_query="some query",
        semantic_min_score=0.75,
    )
    ids = [r["rule_id"] for r in result]
    assert "R-CATCHALL" in ids


def test_filter_semantic_domain_not_passed_when_none(monkeypatch):
    """When no domain is specified, semantic search is called with domain=None."""
    calls = []

    def fake_search(query, top_k, min_score, domain):
        calls.append(domain)
        return []

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    filter_candidates(
        RULES,
        domain=None,
        semantic_query="any query",
    )
    assert calls == [None]





def test_render_rules_as_text_format():
    lean = [
        {
            "rule_id": "R-001",
            "conditions": {"natural_language": "A red car is always a convertible."},
            "reasoning": {"possible_causes": ["data error"]},
            "recommendation": {"action": "Verify in registry."},
        }
    ]
    text = _render_rules_as_text(lean)
    assert "#Rule 1:" in text
    assert "A red car is always a convertible." in text
    assert "**Reason:**" in text
    assert "**Recommendation:**" in text
    assert "Verify in registry." in text


def test_render_rules_as_text_empty():
    assert _render_rules_as_text([]) == ""


def test_render_rules_as_text_multiple_rules():
    lean = [
        {
            "rule_id": "R-A",
            "conditions": {"natural_language": "Rule A condition."},
            "reasoning": {},
            "recommendation": {"action": "Do A."},
        },
        {
            "rule_id": "R-B",
            "conditions": {"natural_language": "Rule B condition."},
            "reasoning": {"possible_causes": ["cause1", "cause2"]},
            "recommendation": {"action": "Do B."},
        },
    ]
    text = _render_rules_as_text(lean)
    assert "#Rule 1:" in text
    assert "#Rule 2:" in text
    assert "cause1, cause2" in text


# ---------------------------------------------------------------------------
# Compressor
# ---------------------------------------------------------------------------


def test_compress_returns_top_k():
    lean = compress(RULES, top_k=1, min_relevance=0.0)
    assert len(lean) == 1


def test_compress_strips_internal_fields():
    rule = {**RULES[0], "author": "alice", "updated_at": "2026-01-01"}
    lean = compress([rule], top_k=5, min_relevance=0.0)
    assert all("author" not in r and "updated_at" not in r for r in lean)
