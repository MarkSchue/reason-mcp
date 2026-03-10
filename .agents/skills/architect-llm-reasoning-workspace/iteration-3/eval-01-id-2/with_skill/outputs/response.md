1) **Recommended architecture**
Primary recommendation: run local-first Python inference with PostgreSQL+pgvector co-located, and allow cloud only via explicit governance gates.

2) **Component diagram in words**
API -> Policy Engine -> Retrieval -> Planner -> Model Gateway -> Verifier -> Audit logger.

3) **Storage design (tables/collections + why)**
- **Knowledge** storage: `knowledge_items`, `knowledge_embeddings` for factual grounding.
- **Planning strategies** storage: `planning_strategies` for reusable decomposition policies and scoring.
- **Capabilities** storage: `capabilities` for action constraints and schemas.
- Example entity: `capabilities(id, name, version, preconditions_json, limits_json, owner, updated_at)`.
- Keep `priority_policies` separate from planning strategy so governance updates do not rewrite execution tactics.

4) **Reasoning/planning flow (step-by-step)**
1. Ingest request and classify sensitivity/complexity.
2. Apply priority policy constraints.
3. Retrieve knowledge + strategies + capabilities.
4. Build and verify plan.
5. Execute and evaluate output.
6. Log outcomes and update strategy scores.

5) **Local vs cloud decision with explicit criteria**
Latency: local wins. Governance: local wins strongly. Cost: local better for steady load, cloud for spikes. Complexity: cloud useful for hardest planning cases.
Decision: choose local-first for your constraints and keep cloud as gated fallback only.

6) **Python stack recommendation**
FastAPI, SQLAlchemy, Alembic, psycopg, pgvector-python, asyncio, structlog, Prometheus client.

7) **Risks and mitigations**
Capacity saturation -> queue and autoscaling.
Embedding drift -> scheduled re-embedding.
Policy misrouting -> simulation tests and immutable audit events.

8) **Implementation roadmap (phased)**
Phase 1: foundation (schema + retrieval + local route).
Phase 2: policy separation + strategy scoring.
Phase 3: hybrid fallback controls + verifier hardening.
KPIs: p95 < 1.5s, compliance incidents 0, fallback rate < 15%, success rate > 88%.
