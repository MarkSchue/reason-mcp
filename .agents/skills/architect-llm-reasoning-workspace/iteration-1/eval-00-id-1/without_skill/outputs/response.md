## Recommended architecture

Use a **policy-grounded planner-executor-verifier loop** around your local SLM, backed by three persistent stores:  
1) domain knowledge, 2) planning strategy memory, and 3) capability metadata.  
Keep the model stateless and push reliability into explicit data, retrieval, validation, and run-time checks.

A good default is a **single Python service** (FastAPI + workers) with clear module boundaries, local-first storage, and full run logging for replay/audit. This gives you deterministic control over planning quality while still using the SLM for flexible reasoning.

---

## Component diagram in words

- **API Layer**: receives task requests and context.
- **Orchestrator**: coordinates plan generation, tool execution, retries, and verification.
- **Retriever**: fetches relevant knowledge, strategies, and capabilities using hybrid search.
- **Planner (SLM prompt program)**: creates a structured plan constrained by policies.
- **Executor**: runs steps against registered tools/capabilities.
- **Verifier/Critic**: checks outcomes against success criteria and safety rules.
- **Memory Writer**: logs run artifacts, outcomes, and feedback to improve future strategy ranking.

---

## Storage design (what to store and why)

Use PostgreSQL as the source of truth (with `pgvector` if needed), or SQLite + local vector DB for smaller deployments.

### 1) Domain knowledge
- `knowledge_items(id, domain, title, content, source, tags, confidence, updated_at, embedding)`
- Purpose: stable operational facts, SOPs, runbooks, constraints, exception handling.
- Retrieval: metadata filter (domain/tags/freshness) + semantic top-k.

### 2) Planning strategies
- `planning_strategies(id, domain, name, strategy_json, preconditions, success_rate, avg_latency_ms, risk_score, version, active, updated_at)`
- Purpose: reusable plan templates/heuristics (e.g., “incident triage”, “rollback-first”, “cost-minimizing”).
- `strategy_json` includes:
  - goal decomposition pattern
  - branching rules
  - stop/retry thresholds
  - escalation conditions

### 3) Capability metadata
- `capabilities(id, name, version, input_schema, output_schema, preconditions, side_effects, limits_json, timeout_s, permissions, owner, health_status, updated_at)`
- Purpose: tells planner what tools exist, when to use them, and constraints.
- Reliability gain: prevents hallucinated tool usage and invalid step generation.

### 4) Runtime + learning logs
- `reasoning_runs(id, task_type, task_payload, selected_strategy_id, plan_json, outcome, error_class, latency_ms, created_at)`
- `step_executions(id, run_id, step_no, capability_id, args_json, result_json, status, latency_ms)`
- `feedback_events(id, run_id, signal_type, signal_value, notes, created_at)`
- Purpose: replay, audit, and strategy scoring.

---

## Reasoning and planning flow

1. **Intake + classify** task (`task_type`, urgency, risk level).  
2. **Retrieve context**:
   - domain facts from `knowledge_items`
   - top strategies for this task type
   - available capabilities satisfying preconditions
3. **Constrained planning**:
   - SLM generates JSON plan only (schema-enforced)
   - planner must reference capability IDs and expected outputs
4. **Static validation**:
   - schema checks, permission checks, dependency ordering, timeout/budget checks
5. **Execute step-by-step**:
   - after each step, verify result against expected state
6. **Critic/verifier pass**:
   - detect contradictions, missing evidence, policy violations
7. **Retry/escalate policy**:
   - bounded retries; fallback strategy if confidence drops
8. **Persist run + score strategy**:
   - update success metrics and promote/demote strategies

---

## Reliability mechanisms (critical)

- **Strict structured outputs** (Pydantic models for plan/step/contracts).
- **Capability allowlist**: planner can only use registered capabilities.
- **Policy separation**:
  - priority policy = what to optimize (speed, safety, cost)
  - strategy = how to solve
- **Deterministic guards** before and after each model call.
- **Confidence + evidence fields** required in plan and final answer.
- **Replayable traces** for debugging and continuous improvement.

---

## Python stack recommendation

- API/orchestration: `FastAPI`, `uvicorn`, `pydantic`, `tenacity`
- Data layer: `SQLAlchemy`, `Alembic`, `psycopg` (or `sqlite` for MVP)
- Retrieval: `pgvector` (or `qdrant-client` for local vector store)
- Queue/workers: `Celery` or `RQ` (optional for async ops tasks)
- Evaluation/telemetry: `OpenTelemetry`, Prometheus client, simple offline eval scripts in Python
- Local model gateway: one adapter interface (`generate_plan`, `critique_plan`, `summarize_outcome`) so you can swap SLMs later without rewiring logic

---

## Implementation roadmap (phased)

1. **Phase 1 (MVP)**: schema + orchestrator + constrained planner + executor + run logging.  
2. **Phase 2**: hybrid retrieval + strategy ranking + verifier + retry policies.  
3. **Phase 3**: offline evaluation harness, automated strategy promotion rules, drift/freshness monitoring for knowledge items.  

This architecture makes reasoning reliable by treating planning intelligence as **data + policy + verification**, not just prompt text.
