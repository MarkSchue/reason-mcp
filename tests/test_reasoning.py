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


def test_filter_matches_on_observation():
    result = filter_candidates(RULES, {"OBS_VEHICLE_SEEN"}, domain="fleet_tracking")
    assert len(result) == 1
    assert result[0]["rule_id"] == "R-001"


def test_filter_excludes_wrong_context_state():
    result = filter_candidates(
        RULES, {"OBS_PRESSURE"}, domain="industrial", context_state="IDLE"
    )
    assert result == []


def test_filter_matches_correct_context_state():
    result = filter_candidates(
        RULES, {"OBS_PRESSURE"}, domain="industrial", context_state="PRODUCTION"
    )
    assert len(result) == 1
    assert result[0]["rule_id"] == "R-002"


def test_filter_keyword_only_rule_matched_by_keyword():
    """R-003 has no observations trigger — should be found via keyword alone."""
    result = filter_candidates(
        RULES, set(), domain="fleet_tracking", keywords={"speed", "highway"}
    )
    ids = [r["rule_id"] for r in result]
    assert "R-003" in ids


def test_filter_keyword_hits_obs_rule_without_observation():
    """R-001 has both obs and keywords; keyword match alone should surface it."""
    result = filter_candidates(
        RULES, set(), domain="fleet_tracking", keywords={"convertible"}
    )
    ids = [r["rule_id"] for r in result]
    assert "R-001" in ids


def test_filter_no_match_wrong_keywords():
    result = filter_candidates(
        RULES, set(), domain="fleet_tracking", keywords={"banana", "cloud"}
    )
    assert result == []


def test_filter_keyword_excluded_by_domain():
    """R-002 is industrial; supplying correct keyword but wrong domain should exclude it."""
    result = filter_candidates(
        RULES, set(), domain="fleet_tracking", keywords={"pressure"}
    )
    ids = [r["rule_id"] for r in result]
    assert "R-002" not in ids


def test_filter_practice_rule_keyword_match():
    """Simulate the user query about Frau Meier and ensure the rule is returned.

    This mirrors the `praxis.json` rule in the knowledge directory.  The loader
    uses a simple file cache; when you add a rule at runtime you must restart or
    call `invalidate_cache()` so the new file is visible.
    """
    practice = {
        "rule_id": "R-PRACTICE",
        "domain": "Praxisbesetzung",
        "active": True,
        "trigger": {"keywords": ["Meier", "Praxisbesetzung"]},
        "conditions": {"natural_language": "Frau Meier arbeitet Dienstag"},
        "reasoning": {"confidence_prior": 0.6},
        "recommendation": {"action": "Versuchen Sie Herrn Müller", "urgency": "medium"},
        "scoring": {"severity": 2},
    }
    # keyword from user message gets normalized to 'meier'
    result = filter_candidates(
        RULES + [practice], set(), keywords={"meier"}
    )
    ids = [r["rule_id"] for r in result]
    assert "R-PRACTICE" in ids


def test_filter_keyword_normalization_removes_diacritics_and_punctuation():
    # rule R-001 has keywords car, vehicle, convertible
    # add a custom rule with a fancy name to verify normalization
    special = {
        "rule_id": "R-NAME",
        "domain": "fleet_tracking",
        "active": True,
        "trigger": {"keywords": ["Fr. Schröder"]},
        "conditions": {"natural_language": "Name match."},
        "reasoning": {"confidence_prior": 0.5},
        "scoring": {"severity": 1},
    }
    result = filter_candidates(
        RULES + [special], set(), domain="fleet_tracking", keywords={"schroder"}
    )
    ids = [r["rule_id"] for r in result]
    assert "R-NAME" in ids


# ---------------------------------------------------------------------------
# Rule text renderer
# ---------------------------------------------------------------------------


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
    lean = compress(RULES, {"OBS_VEHICLE_SEEN", "OBS_PRESSURE"}, top_k=1, min_relevance=0.0)
    assert len(lean) == 1


def test_compress_strips_internal_fields():
    rule = {**RULES[0], "author": "alice", "updated_at": "2026-01-01"}
    lean = compress([rule], {"OBS_VEHICLE_SEEN"}, top_k=5, min_relevance=0.0)
    assert all("author" not in r and "updated_at" not in r for r in lean)


# ---------------------------------------------------------------------------
# Semantic filter (Stage 2) — embedder is mocked to keep tests model-free
# ---------------------------------------------------------------------------


def _sem_rule(rule_id: str, domain: str = "fleet_tracking") -> dict:
    return {
        "rule_id": rule_id,
        "domain": domain,
        "active": True,
        "trigger": {"keywords": []},  # no keyword trigger — only semantic
        "conditions": {"natural_language": f"Condition for {rule_id}."},
        "reasoning": {"confidence_prior": 0.8},
        "scoring": {"severity": 3},
    }


def test_filter_semantic_query_adds_stage2_candidates(monkeypatch):
    """Rules found only by semantic search are included in the candidate set."""
    sem_rule = _sem_rule("R-SEM-001")

    def fake_search(query, index_dir, rules, top_k, min_score, domain):
        return [("R-SEM-001", 0.82)]

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    result = filter_candidates(
        RULES + [sem_rule],
        set(),
        domain="fleet_tracking",
        semantic_query="some query text",
        semantic_min_score=0.75,
        index_dir="/tmp/fake_index",
    )
    ids = [r["rule_id"] for r in result]
    assert "R-SEM-001" in ids
    # Score is attached for downstream ranking
    # _sem_rule has no keyword/obs criteria → catch-all → det_score=0.5
    match = next(r for r in result if r["rule_id"] == "R-SEM-001")
    assert match["_sem_score"] == 0.82
    assert match["_det_score"] == 0.5  # catch-all neutral score from det path


def test_filter_semantic_query_off_by_default():
    """Without semantic_query, a rule with no trigger criteria is a catch-all."""
    sem_rule = _sem_rule("R-SEM-002")
    result = filter_candidates(
        [sem_rule],
        set(),
        domain="fleet_tracking",
    )
    # No criteria on rule → catch-all; should still pass without semantic
    ids = [r["rule_id"] for r in result]
    assert "R-SEM-002" in ids


def test_filter_parallel_union_includes_both_paths(monkeypatch):
    """Catch-all (det path) and semantic-only hit are both in the union.

    In the parallel design neither path gates the other.  A catch-all rule
    (no trigger criteria) is always included by the deterministic path;
    a rule found only by semantic is included by the semantic path.  Both
    appear in the merged candidate set.  Ranking is left to the compressor.
    """
    catch_all = _sem_rule("R-CATCHALL")  # no trigger criteria → always det hit
    targeted = _sem_rule("R-TARGET")     # only returned by semantic path

    def fake_search(query, index_dir, rules, top_k, min_score, domain):
        return [("R-TARGET", 0.91)]

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    result = filter_candidates(
        [catch_all, targeted],
        set(),
        domain="fleet_tracking",
        semantic_query="targeted query",
        semantic_min_score=0.75,
        index_dir="/tmp/fake_index",
    )
    ids = [r["rule_id"] for r in result]
    # Both paths contribute — neither suppresses the other
    assert "R-TARGET" in ids
    assert "R-CATCHALL" in ids
    # Scores are attached correctly
    # Both rules are catch-all (no criteria) → det_score = 0.5 for both
    t = next(r for r in result if r["rule_id"] == "R-TARGET")
    assert t["_sem_score"] == 0.91
    assert t["_det_score"] == 0.5  # catch-all neutral score from det path
    c = next(r for r in result if r["rule_id"] == "R-CATCHALL")
    assert c["_det_score"] == 0.5  # neutral catch-all score
    assert c["_sem_score"] == 0.0


def test_filter_semantic_finds_rule_with_unmatched_keyword_trigger(monkeypatch):
    """Core use case: rule has keyword trigger ["Urlaub", "Krankheit"] but the
    query is about "Hr. Müller montag nicht da".  Det path misses it; semantic
    finds it.  Rule must appear in the union with det_score=0.0, sem_score>0."""
    mueller_rule = {
        "rule_id": "R-MUELLER",
        "domain": "Praxisbesetzung",
        "active": True,
        "trigger": {"keywords": ["Urlaub", "Krankheit"]},  # does NOT match query
        "conditions": {"natural_language": "Hr. Müller arbeitet Do und Fr 08-10 Uhr"},
        "reasoning": {"confidence_prior": 0.95},
        "scoring": {"specificity": 0.9},
    }

    def fake_search(query, index_dir, rules, top_k, min_score, domain):
        # Semantic finds R-MUELLER even though det keywords don't match
        return [("R-MUELLER", 0.78)]

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    result = filter_candidates(
        [mueller_rule],
        set(),  # no observations
        domain="Praxisbesetzung",
        keywords={"montag", "muller", "nicht da"},  # keyword mismatch with trigger
        semantic_query="Hr. Müller montag nicht da",
        semantic_min_score=0.70,
        index_dir="/tmp/fake_index",
    )
    ids = [r["rule_id"] for r in result]
    assert "R-MUELLER" in ids
    match = next(r for r in result if r["rule_id"] == "R-MUELLER")
    assert match["_det_score"] == 0.0   # det path could not match trigger keywords
    assert match["_sem_score"] == 0.78  # semantic path found it


def test_filter_det_path_still_works_when_semantic_fails(monkeypatch):
    """If the embedder raises, the deterministic path result is still returned."""
    def fake_search_error(query, index_dir, rules, top_k, min_score, domain):
        raise RuntimeError("model not available")

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search_error
    )
    result = filter_candidates(
        RULES,
        {"OBS_VEHICLE_SEEN"},
        domain="fleet_tracking",
        semantic_query="some query",
        semantic_min_score=0.75,
        index_dir="/tmp/fake_index",
    )
    ids = [r["rule_id"] for r in result]
    assert "R-001" in ids  # deterministic obs_match still works


def test_filter_semantic_domain_not_passed_when_none(monkeypatch):
    """When no domain is specified, semantic search is called with domain=None."""
    calls = []

    def fake_search(query, index_dir, rules, top_k, min_score, domain):
        calls.append(domain)
        return []

    monkeypatch.setattr(
        "reason_mcp.tools.reasoning.embedder.search_rules", fake_search
    )
    filter_candidates(
        RULES,
        set(),
        domain=None,
        semantic_query="any query",
        index_dir="/tmp/fake_index",
    )
    assert calls == [None]

