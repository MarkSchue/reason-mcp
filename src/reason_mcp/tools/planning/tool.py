"""Planning MCP tool – registers `planning_generate_plan` on the server."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from mcp.server.fastmcp import FastMCP

from reason_mcp.config import config
from reason_mcp.knowledge.loader import get_knowledge
from reason_mcp.session_log import SessionLog
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

        # --- Session log (opt-in via REASON_LOG_REQUESTS) ---
        slog = SessionLog("planning_generate_plan", request_id, timestamp)
        if config.log_requests:
            slog.record_request({
                "request_id": request_id,
                "timestamp": timestamp,
                "goal": goal,
                "domain": domain,
                "context_state": context_state,
                "constraints": constraints,
                "dry_run": dry_run,
            })

        # Load planning knowledge (strategies, skills, component knowledge)
        rules = get_knowledge()
        strategies = [r for r in rules if r.get("type") == "strategy"]
        skills = [r for r in rules if r.get("type") == "skill"]
        if config.log_requests:
            slog.record_step("Step 1 — Knowledge loading", {
                "total_rules": len(rules),
                "strategies": len(strategies),
                "skills": len(skills),
            })

        # Generate execution graph
        graph = generate_graph(goal, strategies, skills, constraints, context_state)
        if config.log_requests:
            slog.record_step("Step 2 — Graph generation", {
                "strategy_id": graph.get("strategy_id"),
                "node_count": len(graph.get("nodes", [])),
                "edge_count": len(graph.get("edges", [])),
                "nodes": [
                    {"id": n.get("id"), "label": n.get("label"), "type": n.get("type")}
                    for n in graph.get("nodes", [])
                ],
            })

        # Dry run simulation
        dry_run_result: dict[str, Any] | None = None
        if dry_run and graph["nodes"]:
            dry_run_result = simulate(graph["nodes"])
        if config.log_requests:
            slog.record_step("Step 3 — Dry-run simulation", {
                "dry_run_enabled": dry_run,
                "nodes_simulated": len(graph.get("nodes", [])) if dry_run else 0,
                "result": dry_run_result,
            })

        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        status = "ok" if graph["nodes"] else "partial"
        if dry_run_result and not dry_run_result["passed"]:
            status = "partial"

        result = {
            "request_id": request_id,
            "status": status,
            "execution_graph": graph,
            "dry_run_result": dry_run_result,
            "meta": {
                "knowledge_version": "arangodb",
                "latency_ms": latency_ms,
                "strategy_used": graph.get("strategy_id"),
                "trace_id": trace_id,
            },
        }
        if config.log_requests:
            slog.record_decision(
                f"status={status!r}: graph has {len(graph.get('nodes', []))} node(s), "
                f"strategy={graph.get('strategy_id')!r}, "
                f"dry_run_passed={dry_run_result.get('passed') if dry_run_result else 'n/a'}."
            )
            slog.record_result(result)
            log_path = slog.write(config.output_dir)
            logger.info("session_log_written", path=str(log_path), request_id=request_id)
        return result
