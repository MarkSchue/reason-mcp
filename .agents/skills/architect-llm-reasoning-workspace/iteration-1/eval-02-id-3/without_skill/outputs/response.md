A solid hybrid design is a **policy-driven router** with strict local-first guards, not a simple “if sensitive then local” switch.

## 1) Core architecture

- **Planner/Router layer** (single decision point): classifies each task, applies policy, chooses local vs cloud.
- **Execution adapters**:
  - `LocalExecutor` for sensitive or low-latency jobs.
  - `CloudExecutor` for high-complexity planning.
- **Strategy store**: versioned repository of routing/policy strategies, loaded at runtime.
- **Telemetry loop**: logs decision inputs, chosen route, outcome, latency, cost, and policy version.

This gives you controllability, auditability, and safe rollout.

## 2) Strategy storage design (Python)

Use a layered store with explicit versioning:

- **Authoritative format**: YAML/JSON strategy specs in Git (reviewable, diffable).
- **Runtime cache**: SQLite (fast lookup, offline safe).
- **Hot reload**: watch file or poll config service; atomically swap active strategy.
- **Version pinning**: every request carries `strategy_version` to make decisions reproducible.
- **Signatures/checksums**: verify config integrity before activation.

Suggested schema:

```python
from dataclasses import dataclass
from typing import Literal, Dict, Any, List

@dataclass(frozen=True)
class Strategy:
    id: str
    version: str
    enabled: bool
    hard_constraints: Dict[str, Any]   # e.g. {"pii": "local_only"}
    weights: Dict[str, float]          # e.g. {"quality": 0.5, "latency": -0.2, "cost": -0.3}
    thresholds: Dict[str, float]       # e.g. {"min_cloud_complexity": 0.7}
    fallback_order: List[Literal["local", "cloud"]]
```

Keep policy data external to code so behavior changes do not require redeploy.

## 3) Prioritization policy model

Use a **two-stage policy**:

### Stage A: hard constraints (deny/allow gates)
Examples:
- Data classification is `restricted` → force local.
- Tenant policy disallows cloud region → force local.
- Cloud outage / budget cap exceeded → force local.
- Local model unavailable for required capability → allow cloud if compliant.

### Stage B: utility scoring (soft optimization)
Compute per-route utility:
\[
U(route)=w_q Q - w_l L - w_c C + w_r R
\]
Where:
- \(Q\): expected quality
- \(L\): latency
- \(C\): cost
- \(R\): reliability/confidence margin

Pick highest utility among routes that passed Stage A.

Policy inputs should include:
- sensitivity level
- complexity estimate
- SLA target
- user/tenant priority
- remaining budget/quota
- recent model reliability

## 4) Routing logic in Python (clean boundaries)

Define clear interfaces:

```python
from typing import Protocol, Dict, Any

class PolicyEngine(Protocol):
    def decide(self, task: Dict[str, Any]) -> Dict[str, Any]: ...

class Executor(Protocol):
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]: ...
```

Decision output should be explicit and auditable:

```python
decision = {
    "route": "local",                  # or "cloud"
    "reason_codes": ["PII_LOCAL_ONLY"],
    "strategy_id": "hybrid-default",
    "strategy_version": "2026-03-01",
    "fallback": ["cloud"]              # optional
}
```

Recommended flow:
1. Classify task (`sensitivity`, `complexity`, `intent`).
2. Evaluate hard constraints.
3. Score allowed routes.
4. Execute selected route.
5. On failure, follow deterministic fallback chain.
6. Record decision + outcome for policy tuning.

## 5) Safety and operations (important)

- **Fail-closed for sensitive classes**: if classifier confidence is low, treat as sensitive.
- **Circuit breakers** for cloud/local providers.
- **Shadow mode** for new policies: evaluate but do not enforce initially.
- **A/B strategy rollout** by tenant or traffic percentage.
- **Decision audit log** with immutable event IDs.
- **Policy tests**: unit tests for edge rules (PII, quota exceeded, outages).

## 6) Practical default policy to start

- Route local when: `sensitivity >= confidential` OR `task_type in [redaction, pii_extraction]`.
- Route cloud when: `complexity > 0.75` AND `sensitivity <= internal` AND `budget_ok`.
- If cloud fails: retry once in alternate region, else local degraded mode.
- If local fails on non-sensitive high-complexity task: escalate to cloud if policy allows.

This baseline is simple, auditable, and extensible without rewriting core routing code.
