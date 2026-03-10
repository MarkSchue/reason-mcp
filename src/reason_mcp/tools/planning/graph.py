"""Execution Graph Generator (REQ-027).

Translates a goal + strategy + available skills into a dependency graph (DAG)
where each node declares its own pre/post conditions and `wait_for` links.

MVP: stub implementation — generates a simple linear graph from a matching
strategy. Extend with real strategy matching in subsequent iterations.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def generate_graph(
    goal: str,
    strategies: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
    context_state: str | None,
) -> dict[str, Any]:
    """
    Build a minimal execution graph for *goal*.

    Returns a dict matching the ExecutionGraph model.
    """
    # Find first matching strategy by keyword (MVP heuristic)
    strategy = next(
        (s for s in strategies if goal.lower() in s.get("keywords", [])),
        strategies[0] if strategies else None,
    )

    if not strategy:
        logger.warning("no strategy found for goal", goal=goal)
        return {"nodes": [], "entry_node_id": "", "strategy_id": None}

    # Build linear nodes from strategy steps
    steps: list[dict[str, Any]] = strategy.get("steps", [])
    nodes: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        node_id = f"node_{i:02d}"
        nodes.append(
            {
                "node_id": node_id,
                "action": step.get("action", "unknown"),
                "pre_conditions": step.get("pre_conditions", []),
                "post_conditions": step.get("post_conditions", []),
                "wait_for": [f"node_{(i - 1):02d}"] if i > 0 else [],
                "timeout_s": step.get("timeout_s"),
            }
        )

    entry = nodes[0]["node_id"] if nodes else ""
    logger.info("graph generated", goal=goal, nodes=len(nodes), strategy=strategy.get("id"))
    return {"nodes": nodes, "entry_node_id": entry, "strategy_id": strategy.get("id")}
