"""Pydantic models and type aliases for the reasoning tool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class Observation(BaseModel):
    """A single normalised observation passed by the Host LLM."""

    observation_id: str = Field(..., min_length=1, max_length=128)
    value: int | float | str | bool
    unit: str | None = Field(None, max_length=16)
    quality: str | None = Field(None, pattern="^(good|uncertain|bad)$")
    observation_type: str | None = Field(None, max_length=64)
    source: str | None = Field(None, max_length=64)


class ReasoningOptions(BaseModel):
    top_k: int = Field(default=3, ge=1, le=10)
    min_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    max_summary_chars: int = Field(default=900, ge=200, le=5000)
    language: str = Field(default="en", pattern="^[a-z]{2}$")
    # Semantic retrieval runs for every request.
    # Calibrated for paraphrase-multilingual-MiniLM-L12-v2: related fact-rules
    # typically score 0.45–0.75 with this model; the old 0.75 default cut all hits.
    semantic_min_score: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity (0..1) for a semantic hit to be accepted.",
    )


def _default_reasoning_options() -> ReasoningOptions:
    return ReasoningOptions()


class AnalyzeContextRequest(BaseModel):
    """Input contract for `reasoning_analyze_context`."""

    request_id: str = Field(..., min_length=1, max_length=128)
    timestamp: str  # ISO 8601
    domain: str | None = Field(None, max_length=64)
    subject_id: str | None = Field(None, max_length=64)
    context_state: str | None = Field(None, max_length=64)
    observations: list[Observation] = Field(default_factory=list, max_length=512)
    keywords: list[str] | None = Field(
        None,
        description=(
            "Lowercase keywords extracted from a natural-language query "
            "(e.g. ['car', 'weight']).  Used for semantic rule matching when "
            "no structured observation IDs are available."
        ),
    )
    options: ReasoningOptions = Field(default_factory=_default_reasoning_options)
    context: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class RuleConditions(BaseModel):
    """The conditions of a domain rule as stored—handed verbatim to the LLM.

    Facts are expressed directly here: physical constants and domain-specific
    values appear in `exact` predicates or in `natural_language` text.
    """

    exact: list[dict[str, Any]] | None = None
    natural_language: str | None = None


class CandidateKnowledge(BaseModel):
    """A single retrieved and lean-stripped domain rule ready for LLM injection."""

    rank: int = Field(..., ge=1)
    rule_id: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    severity: int | None = Field(None, ge=1, le=5)
    reason_text: str
    action_recommendation: str | None = None
    conditions: RuleConditions
    tags: list[str] = Field(default_factory=list)


class ReasoningMeta(BaseModel):
    knowledge_version: str
    latency_ms: float
    candidate_count: int
    matched_count: int
    applied_policies: list[str] = Field(default_factory=list)
    trace_id: str | None = None


class AnalyzeContextResult(BaseModel):
    """The lean knowledge payload returned to the Host LLM for reasoning."""

    candidate_knowledge: list[CandidateKnowledge] = Field(default_factory=list)
    summary_for_llm: str
    no_match_reason: str | None = None


class AnalyzeContextResponse(BaseModel):
    request_id: str
    status: str  # ok | partial | error
    result: AnalyzeContextResult | None = None
    meta: ReasoningMeta | None = None
    errors: list[dict[str, str]] = Field(default_factory=list)
