"""Planning MCP tool – registers `planning_generate_plan` on the server."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from reason_mcp.config import config
from reason_mcp.knowledge.loader import get_knowledge
from reason_mcp.tools.planning.graph import generate_graph
from reason_mcp.tools.planning.simulator import simulate

logger = structlog.get_logger(__name__)


def register(mcp: FastMCP) -> None:
    """Attach the planning tool to the MCP server instance."""

    @mcp.tool(
        name="planning_generate_plan",
        description=(
            "Generate a validated execution graph (DAG) for a given goal. "
            "Runs a dry-run simulation over the graph before returning it, "
            "verifying pre/post-conditions node-by-node without executing any "
            "real-world actions. Returns the graph and the simulation result."
        ),
    )
    def generate_plan(
        request_id: str,
        timestamp: str,
        goal: str,
        domain: str | None = None,
        context_state: str | None = None,
        constraints: list[dict[str, Any]] | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        Args:
            request_id: Caller-generated ID for traceability.
            timestamp: ISO 8601 timestamp.
            goal: Natural-language description of the planning goal.
            domain: Optional domain hint.
            context_state: Optional current system state.
            constraints: Optional list of {field, op, value} constraints.
            dry_run: When True (default) simulate graph before returning.
        """
        t0 = time.monotonic()
        trace_id = str(uuid.uuid4())[:8]
        constraints = constraints or []

        # Load planning knowledge (strategies, skills, component knowledge)
        rules = get_knowledge(config.knowledge_dir)
        strategies = [r for r in rules if r.get("type") == "strategy"]
        skills = [r for r in rules if r.get("type") == "skill"]

        # Generate execution graph
        graph = generate_graph(goal, strategies, skills, constraints, context_state)

        # Dry run simulation
        dry_run_result: dict[str, Any] | None = None
        if dry_run and graph["nodes"]:
            dry_run_result = simulate(graph["nodes"])

        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        status = "ok" if graph["nodes"] else "partial"
        if dry_run_result and not dry_run_result["passed"]:
            status = "partial"

        return {
            "request_id": request_id,
            "status": status,
            "execution_graph": graph,
            "dry_run_result": dry_run_result,
            "meta": {
                "knowledge_version": "json-file",
                "latency_ms": latency_ms,
                "strategy_used": graph.get("strategy_id"),
                "trace_id": trace_id,
            },
        }
