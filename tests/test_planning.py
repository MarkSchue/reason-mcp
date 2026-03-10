"""Tests for the planning pipeline stages."""

from __future__ import annotations

from reason_mcp.tools.planning.simulator import simulate


NODES = [
    {
        "node_id": "node_00",
        "action": "OPEN_VALVE",
        "pre_conditions": [{"field": "valve_state", "op": "==", "value": "CLOSED"}],
        "post_conditions": [{"field": "valve_state", "value": "OPEN"}],
        "wait_for": [],
    },
    {
        "node_id": "node_01",
        "action": "START_PUMP",
        "pre_conditions": [{"field": "valve_state", "op": "==", "value": "OPEN"}],
        "post_conditions": [{"field": "pump_state", "value": "RUNNING"}],
        "wait_for": ["node_00"],
    },
]


def test_simulate_passes_on_correct_initial_state():
    result = simulate(NODES, initial_state={"valve_state": "CLOSED"})
    assert result["passed"] is True
    assert result["simulated_state"]["pump_state"] == "RUNNING"


def test_simulate_captures_violation_on_bad_initial_state():
    result = simulate(NODES, initial_state={"valve_state": "OPEN"})
    # node_00 pre_condition expects CLOSED but state is OPEN → violation on first check
    # After applying post_conditions it becomes OPEN, so node_01 should pass
    assert result["passed"] is False
    assert len(result["violations"]) >= 1


def test_simulate_empty_graph():
    result = simulate([])
    assert result["passed"] is True
    assert result["violations"] == []
