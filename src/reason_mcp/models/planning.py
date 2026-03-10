"""Pydantic models for the planning tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class PlanningConstraint(BaseModel):
    field: str
    op: str
    value: Any


class GeneratePlanRequest(BaseModel):
    """Input contract for `planning_generate_plan`."""

    request_id: str = Field(..., min_length=1, max_length=128)
    timestamp: str
    goal: str = Field(..., min_length=1, max_length=1024)
    domain: str | None = Field(None, max_length=64)
    context_state: str | None = Field(None, max_length=64)
    constraints: list[PlanningConstraint] = Field(default_factory=list)
    dry_run: bool = True


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class ExecutionNode(BaseModel):
    """One node in the execution graph (DAG)."""

    node_id: str
    action: str
    pre_conditions: list[dict[str, Any]] = Field(default_factory=list)
    post_conditions: list[dict[str, Any]] = Field(default_factory=list)
    wait_for: list[str] = Field(default_factory=list)  # node_ids that must complete first
    timeout_s: int | None = None


class ExecutionGraph(BaseModel):
    nodes: list[ExecutionNode]
    entry_node_id: str
    strategy_id: str | None = None


class DryRunResult(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)
    simulated_state: dict[str, Any] = Field(default_factory=dict)


class PlanningMeta(BaseModel):
    knowledge_version: str
    latency_ms: float
    strategy_used: str | None = None
    trace_id: str | None = None


class GeneratePlanResponse(BaseModel):
    request_id: str
    status: str  # ok | partial | error
    execution_graph: ExecutionGraph | None = None
    dry_run_result: DryRunResult | None = None
    meta: PlanningMeta | None = None
    errors: list[dict[str, str]] = Field(default_factory=list)
