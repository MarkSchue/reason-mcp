"""Dry Run Simulator (REQ-025).

Walks the execution graph node-by-node, applying post_condition mutations
to a simulated state dict and asserting pre_conditions before each step.
No real-world actions are taken.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _evaluate_condition(cond: dict[str, Any], state: dict[str, Any]) -> bool:
    """Evaluate a simple {field, op, value} condition against *state*."""
    field = cond.get("field", "")
    op = cond.get("op", "==")
    expected = cond.get("value")
    actual = state.get(field)
    match op:
        case "==": return actual == expected
        case "!=": return actual != expected
        case ">":  return actual is not None and actual > expected
        case ">=": return actual is not None and actual >= expected
        case "<":  return actual is not None and actual < expected
        case "<=": return actual is not None and actual <= expected
        case _:    return False


def simulate(
    nodes: list[dict[str, Any]],
    initial_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Simulate the execution graph.

    Returns {passed: bool, violations: list[str], simulated_state: dict}.
    """
    state = dict(initial_state or {})
    violations: list[str] = []

    for node in nodes:
        node_id = node["node_id"]

        # Check pre-conditions
        for cond in node.get("pre_conditions", []):
            if not _evaluate_condition(cond, state):
                msg = (
                    f"[{node_id}] pre_condition failed: "
                    f"{cond.get('field')} {cond.get('op')} {cond.get('value')} "
                    f"(actual={state.get(cond.get('field', ''))})"
                )
                violations.append(msg)
                logger.warning("pre_condition violation", node=node_id, cond=cond)

        # Apply post-condition mutations (state changes the step would produce)
        for mutation in node.get("post_conditions", []):
            field = mutation.get("field")
            val = mutation.get("value")
            if field:
                state[field] = val

    passed = len(violations) == 0
    logger.info("dry run complete", passed=passed, violations=len(violations))
    return {"passed": passed, "violations": violations, "simulated_state": state}
