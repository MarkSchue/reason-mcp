1) **Recommended architecture**
Primary recommendation: adopt a local-first Python architecture with a policy-driven planner-executor-verifier loop and explicit strategy memory.

2) **Component diagram in words**
FastAPI API -> Orchestrator -> Policy Engine -> Retrieval -> Planner -> Executor -> Verifier -> Telemetry.

3) **Storage design (tables/collections + why)**
- **Knowledge** storage: `knowledge_items`, `knowledge_embeddings`; purpose is grounded domain recall.
- **Planning strategies** storage: `planning_strategies`; purpose is reusable execution templates and strategy scoring.
- **Capabilities** storage: `capabilities`; purpose is tool metadata, preconditions, and safety limits.
- Example entity: `planning_strategies(id, domain, strategy_json, version, score_quality, score_reliability, updated_at)`.
- Priority policy is stored separately in `priority_policies` to define objectives, while planning strategy defines execution method.

4) **Reasoning/planning flow (step-by-step)**
1. Classify task and sensitivity.
2. Load priority policy and hard constraints.
3. Retrieve knowledge, planning strategy, and capabilities.
4. Generate plan and verify constraints.
5. Execute steps with checkpoints.
6. Persist run trace and rescore strategy.

5) **Local vs cloud decision with explicit criteria**
Latency: local is lower and more predictable. Governance: local keeps sensitive data in-boundary. Cost: local is steadier at sustained volume, cloud helps bursty usage. Complexity: cloud can help hardest synthesis tasks.
Decision: local-first with policy-gated cloud fallback for low-sensitivity high-complexity tasks only.

6) **Python stack recommendation**
FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL+pgvector, Redis, Celery/RQ, OpenTelemetry, pytest.

7) **Risks and mitigations**
Risk: stale knowledge -> freshness TTL and confidence filters.
Risk: strategy drift -> versioned strategies with canary rollout.
Risk: unsafe routing -> deny-by-default cloud policy and verifier checks.

8) **Implementation roadmap (phased)**
Phase 1: core API + schema + local model gateway.
Phase 2: policy engine + strategy scorer + verifier loop.
Phase 3: governed hybrid fallback and observability hardening.
KPIs: p95 latency < 2.0s, policy violations = 0, task success > 90%, verifier pass rate > 95%.
