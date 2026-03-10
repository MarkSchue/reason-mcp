# Python Reasoning Architecture Reference

Use this reference when detailed architecture depth is needed.

## 1) Recommended deployment patterns

### A. Local-first
- Model runs on local GPU/CPU.
- Database and vector index are local.
- Best for privacy, predictable latency, and offline operation.

### B. Cloud-first
- Model endpoint is remote.
- Use managed PostgreSQL + managed vector store.
- Best for elastic scale and easier operations.

### C. Hybrid
- Router chooses local or cloud model by task sensitivity/complexity.
- Local store for sensitive data, cloud for non-sensitive enrichment.

## 2) Core Python stack

- API: `FastAPI`
- Background jobs: `Celery` or `RQ`
- Relational data: `PostgreSQL` + `SQLAlchemy`
- Migrations: `Alembic`
- Vector search: `pgvector` (preferred if already on Postgres) or `Qdrant`
- Caching: `Redis`
- Observability: `OpenTelemetry` + structured logging

## 3) Minimal flow

1. Receive task.
2. Classify domain and constraints.
3. Retrieve policies, capabilities, and relevant knowledge.
4. Build plan using planner policy.
5. Execute with tool calls.
6. Verify outcome.
7. Persist run + feedback + updated strategy score.

## 4) Strategy scoring model

Track per-strategy metrics:
- success rate,
- mean latency,
- cost per success,
- safety/compliance incidents.

Simple score:

`score = w1*success - w2*latency - w3*cost - w4*incident_rate`

Maintain domain-specific weights.

## 5) Suggested schema snippets

```python
from sqlalchemy import Column, String, JSON, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class PlanningStrategy(Base):
    __tablename__ = "planning_strategies"
    id = Column(String, primary_key=True)
    domain = Column(String, index=True, nullable=False)
    strategy_json = Column(JSON, nullable=False)
    score = Column(Float, default=0.0)
    updated_at = Column(DateTime, nullable=False)

class ReasoningRun(Base):
    __tablename__ = "reasoning_runs"
    id = Column(String, primary_key=True)
    task = Column(String, nullable=False)
    plan_json = Column(JSON, nullable=False)
    outcome = Column(String, nullable=False)
    latency_ms = Column(Float, nullable=False)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, nullable=False)

class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("reasoning_runs.id"), index=True)
    signal_type = Column(String, nullable=False)
    signal_value = Column(Float, nullable=False)
    notes = Column(String)
    created_at = Column(DateTime, nullable=False)
```

## 6) Integration heuristics

Use these defaults unless user constraints override them:
- Need <250ms response and stable workload: local-first.
- Need strong peak scaling or broad model capability: cloud-first.
- Need strict data zoning + advanced tasks: hybrid.

## 7) Failure handling

- Retry retrieval with narrower filters on low-confidence matches.
- Fall back to baseline strategy if selected strategy confidence is low.
- Route to deterministic rule engine for high-risk decisions.
- Persist error class and recovery path for future policy tuning.

## 8) Governance and safety

- Persist decision traces for each run.
- Store data lineage (`source`, `timestamp`, `confidence`).
- Enforce PII redaction before cloud calls when needed.
- Version policies and support rollback.
