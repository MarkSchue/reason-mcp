1) **Recommended architecture**
Primary recommendation: local-first Python architecture with policy-driven planner-executor-verifier loop and explicit strategy/policy stores.

2) **Component diagram in words**
FastAPI -> Orchestrator -> Policy Engine -> Retriever -> Planner -> Executor -> Verifier -> Telemetry.

3) **Storage design (tables/collections + why)**
Use `knowledge_items`, `capabilities`, `priority_policies`, `planning_strategies`, `reasoning_runs`, `feedback_events`.
Example entity: `planning_strategies(id, domain, strategy_json, version, score_quality, score_reliability, updated_at)`.
Why: policy defines objectives; strategy defines execution method.

4) **Reasoning/planning flow (step-by-step)**
1. Classify task and sensitivity.
2. Load priority policy.
3. Retrieve knowledge + capabilities + top strategy.
4. Generate and verify plan.
5. Execute steps with checkpoints.
6. Log outcomes and re-score strategy.

5) **Local vs cloud decision with justification**
Criteria: latency (local lower), governance (local stronger), cost (local better at steady load), complexity (cloud can help hardest tasks).
Decision: local-first with policy-gated cloud fallback only for allowed low-sensitivity high-complexity tasks.

6) **Python stack recommendation**
FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL+pgvector, Redis, Celery/RQ, OpenTelemetry.

7) **Risks and mitigations**
Risk: stale knowledge -> freshness TTL + source confidence.
Risk: policy/strategy drift -> versioning + canary rollout.
Risk: unsafe routing -> deny-by-default cloud policy.

8) **Implementation roadmap (phased)**
Phase 1: Core pipeline + schema.
Phase 2: Verifier + policy separation.
Phase 3: Strategy scoring loop.
KPIs: p95 latency < 2s, policy violations = 0, task success > 85%.
