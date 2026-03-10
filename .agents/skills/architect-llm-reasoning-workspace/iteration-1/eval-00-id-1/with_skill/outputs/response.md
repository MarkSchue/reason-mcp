1) **Recommended architecture (1-2 paragraphs)**  
Use a Python-only, local-first architecture with a **reasoning loop around a local SLM**, not a single prompt pipeline. The core pattern is: retrieve domain facts + retrieve prior successful strategies + retrieve capability constraints, then plan, execute tools, verify, and write outcomes back to memory. This makes reasoning more reliable because the model is grounded by explicit artifacts (knowledge, policy, and capability metadata) instead of relying on latent memory alone.

Implement this as a modular service: `FastAPI` entrypoint, an orchestrator that runs `planner -> executor -> verifier`, a model gateway for local inference, and persistent stores for structured data + vectors + run telemetry. Keep planning strategies and priority policies versioned and scored so the system can promote effective plans over time and fall back to safe defaults when uncertainty is high.

2) **Component diagram in words**  
`Client/API` -> `Task Intake (FastAPI + Pydantic validation)` -> `Orchestrator`  
`Orchestrator` calls:  
- `Context Builder` (task normalization, objective extraction)  
- `Retriever` (knowledge + strategies + capabilities + policies)  
- `Planner (SLM)` (creates executable plan with rationale + confidence)  
- `Capability Router` (maps plan steps to available tools with precondition checks)  
- `Executor` (runs Python tools/workflows)  
- `Verifier/Critic` (checks policy, constraints, and result quality)  
Then writes to:  
- `Run Logger` (reasoning trace, outcome, metrics)  
- `Strategy Scorer` (updates strategy performance)  
- `Memory Writer` (stores new validated knowledge/lessons)  
Finally returns: `response + explanation + audit metadata`.

3) **Storage design (tables/collections + why)**  
Use `PostgreSQL + pgvector` (or `SQLite + sqlite-vss` for smaller offline deployments). Recommended tables:

- `knowledge_items` (`id`, `domain`, `title`, `content`, `source`, `tags`, `confidence`, `valid_from`, `valid_to`, `updated_at`)  
  - Why: durable domain facts with provenance and validity windows.
- `knowledge_embeddings` (`knowledge_id`, `embedding`, `model`, `chunk_index`)  
  - Why: semantic retrieval over long text chunks.
- `capabilities` (`id`, `name`, `version`, `description`, `input_schema`, `output_schema`, `preconditions`, `limits`, `sensitivity_level`, `owner`)  
  - Why: explicit machine-readable tool metadata for safe planning.
- `planning_strategies` (`id`, `domain`, `strategy_json`, `assumptions`, `success_rate`, `avg_latency_ms`, `risk_score`, `is_default`, `version`, `updated_at`)  
  - Why: reusable plan templates/heuristics with measurable quality.
- `priority_policies` (`id`, `domain`, `objective_weights_json`, `hard_constraints_json`, `effective_from`, `effective_to`, `version`)  
  - Why: separates “what to optimize” from “how to plan”.
- `reasoning_runs` (`id`, `task`, `context_hash`, `plan_json`, `selected_strategy_id`, `outcome`, `confidence`, `latency_ms`, `token_count`, `created_at`)  
  - Why: full auditability and reproducibility.
- `execution_steps` (`id`, `run_id`, `step_no`, `capability_id`, `input_json`, `output_json`, `status`, `error`)  
  - Why: step-level debugging and reliability analysis.
- `feedback_events` (`id`, `run_id`, `signal_type`, `signal_value`, `notes`, `created_at`)  
  - Why: human/system feedback loop for strategy updates.

4) **Reasoning/planning flow (step-by-step)**  
1. Ingest request and classify domain + urgency + sensitivity.  
2. Load active `priority_policies` for that domain.  
3. Retrieve top-k domain knowledge (hybrid: metadata filter + vector search).  
4. Retrieve top strategies by domain and recent score; include default fallback.  
5. Retrieve relevant capabilities and enforce preconditions/limits before planning.  
6. Build planning prompt with: objective weights, constraints, retrieved facts, capability list, and required output schema.  
7. Generate candidate plan(s) with confidence; pick best via verifier scoring rules.  
8. Execute each step through capability router; capture structured outputs/errors.  
9. Run critic/verifier for constraint compliance and objective satisfaction.  
10. If failed and retry budget remains, re-plan with failure context; else return safe fallback response.  
11. Persist run trace, step telemetry, and feedback signal.  
12. Re-score strategy and update promotion/demotion thresholds.

5) **Local vs cloud decision with justification**  
Choose **local-first** as primary: local SLM inference + local database + local vector index. This matches operations-assistant needs for privacy, deterministic latency on internal networks, and lower recurring cost. It also improves governance because capability metadata and reasoning traces remain on-prem.

Use an optional **hybrid fallback** only for explicitly allowed low-sensitivity tasks when local confidence is below threshold or context length exceeds local model limits. Route by policy (`sensitivity_level`, confidence, SLA). This preserves reliability while avoiding hard dependency on cloud availability.

6) **Python stack recommendation**  
- API/orchestration: `FastAPI`, `Pydantic`, `Uvicorn`  
- Workflow/state machine: `LangGraph` (or custom Python state machine with typed nodes)  
- Local SLM runtime: `llama-cpp-python` (fully local) or `vLLM` Python serving stack  
- Data/ORM/migrations: `SQLAlchemy 2.x`, `Alembic`, `psycopg`  
- Vector search: `pgvector` via SQLAlchemy extension  
- Background jobs: `Celery` or `RQ` for asynchronous execution/scoring  
- Caching: `Redis` (plan/result and retrieval cache)  
- Observability: `OpenTelemetry` + `structlog` + `Prometheus` client  
- Evaluation/testing: `pytest`, `hypothesis` (policy and planner invariants)

7) **Risks and mitigations**  
- Retrieval drift or stale knowledge -> enforce `valid_to`, freshness scoring, and source confidence thresholds.  
- Planner hallucinating unavailable tools -> hard capability gating and schema-validated tool calls only.  
- Strategy overfitting to recent runs -> keep default baseline strategy and use rolling-window scoring.  
- Silent policy violations -> mandatory verifier stage with hard-fail constraints before final response.  
- Local model quality limits -> confidence thresholds, re-plan policy, optional hybrid escalation path.  
- Trace growth and storage bloat -> retention tiers, archive old traces, compact embeddings by policy.

8) **Implementation roadmap (phased)**  
- **Phase 1 (MVP core):** FastAPI intake, local SLM gateway, PostgreSQL schema (`knowledge`, `capabilities`, `strategies`, `runs`), basic retrieve-plan-execute loop.  
- **Phase 2 (Reliability):** Add verifier/critic, capability precondition engine, structured step logging, retry/re-plan logic, policy versioning.  
- **Phase 3 (Learning loop):** Strategy scoring service, feedback ingestion, automatic promote/demote of strategies, retrieval quality metrics.  
- **Phase 4 (Hardening):** Observability dashboards, performance tuning, retention/archival, chaos testing for tool failures.  
- **Phase 5 (Hybrid optional):** Policy-based cloud fallback router for allowed tasks, with full audit parity and strict sensitivity guards.
