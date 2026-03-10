1) **Recommended architecture**
Primary recommendation: deploy a hybrid Python control plane with strict local default and policy-evaluated cloud escalation for complex non-sensitive tasks.

2) **Component diagram in words**
FastAPI -> Task Classifier -> Policy Engine -> Strategy Selector -> Model Gateway(local/cloud) -> Verifier -> Telemetry scorer.

3) **Storage design (tables/collections + why)**
- **Knowledge** storage: `knowledge_items` and vector embeddings for context retrieval.
- **Planning strategies** storage: `planning_strategies` and `strategy_scores` for adaptive plan selection.
- **Capabilities** storage: `capabilities` for executable tool metadata and guardrails.
- Example entity: `priority_policies(id, objective_weights_json, hard_constraints_json, version, effective_from)`.
- Separation rule: priority policy governs objective weighting; planning strategy governs execution path.

4) **Reasoning/planning flow (step-by-step)**
1. Classify task sensitivity and complexity.
2. Load active priority policy.
3. Retrieve knowledge, capabilities, and top strategy.
4. Route local/cloud via policy thresholds.
5. Execute and verify outputs.
6. Persist telemetry and rescore strategies.

5) **Local vs cloud decision with explicit criteria**
Latency: local lower jitter. Governance: local stronger compliance posture. Cost: local better for sustained throughput; cloud helps burst workloads. Complexity: cloud can improve deep synthesis tasks.
Decision: hybrid with local-by-default and explicit cloud allow-list.

6) **Python stack recommendation**
FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL+pgvector, Celery, Redis, OpenTelemetry, pytest.

7) **Risks and mitigations**
Cloud leakage -> redaction and deny-by-default routing.
Policy contradiction -> policy linting and staged rollout.
Strategy overfitting -> holdout evaluation and rolling score windows.

8) **Implementation roadmap (phased)**
Phase 1: local core pipeline.
Phase 2: policy/strategy separation and router.
Phase 3: governed cloud fallback and reliability tuning.
KPIs: success rate > 90%, policy violations 0, p99 < 4s, verifier-pass > 95%.
