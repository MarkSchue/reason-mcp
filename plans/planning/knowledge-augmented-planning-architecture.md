# Knowledge-Augmented Planning Architecture Plan

## 1) Recommended architecture (1-2 paragraphs)

Primary recommendation: build a **local-first, deterministic MCP planning service** that consumes goals, constraints, and reasoning outputs (from the separate Reasoning MCP) to generate, validate, and manage execution plans. The Planning system operates on a state machine (`draft`, `approved`, `executing`, `completed`, `failed`) and uses a strict fallback policy. The planner relies entirely on the Reasoning system for understanding the state of the world, maintaining a clean boundary.

For the MVP, use dedicated MCP endpoints (`planning.generate_plan`, `planning.simulate_and_validate`, and `planning.update_status`) to manage the lifecycle of a plan. Strategies and priority policies are stored separately from physical domain knowledge. Planning steps use an execution graph format (with `wait_for` tags) instead of a simple linear list, translating well to industrial environments (like SPS/PLC).

---

## 2) Component diagram in words

Request path (planning-first):

1. **Host LLM / Agent** sends a goal, constraints, and current context (including reasoning insights) to the Planning MCP.
2. **MCP API Layer** validates the schema and limits.
3. **Knowledge & Strategy Loader** loads versioned planning strategies, priority policies, and strict `component_knowledge` (hardware/domain facts) from JSON/SQLite.
4. **Goal/Constraint Engine** maps the requested goal to available strategies restricting actions to known component tolerances.
5. **Plan Generator** drafts an Execution Graph of executable steps (with distinct `pre_conditions` and `post_conditions` mapping).
6. **Dry Run Simulator (Safety Validator)** simulates state mutations across all steps. Rejects plans violating capability limits, logic rules, or `pre_conditions`.
7. **State Machine Manager** records the plan in a `draft` state and prepares it for approval.
8. **Plan Monitor / Replanner** (on update) tracks step-by-step execution graph nodes, transitioning the state machine and triggering replanning if constraints are violated.
9. **Execution Logger** stores the plan trajectory and outcomes for future strategy evaluation.

---

## 3) Storage design (tables/collections + why)

### Planning strategies storage: tables/collections and purpose

**Now (JSON files):**
- `policies/planning_strategies.json`: Defines step-by-step templates for resolving specific goals.

**Later (SQLite):**
- `planning_strategies(id, domain, strategy_name, goal_tags, strategy_json, success_score, active, created_at, updated_at)`

Purpose: Store the templates and procedural logic required to achieve a goal.

### Priority policies storage: tables/collections and purpose

**Now (JSON files):**
- `policies/priority_policies.json`: Defines constraints like "safety over speed" or "budget caps".

**Later (SQLite):**
- `priority_policies(id, objective, policy_json, effective_from, effective_to, active)`

Purpose: Maintain business priorities and constraints that override or guide strategy selection.

### Component Knowledge storage: tables/collections and purpose

**Now (JSON files):**
- `knowledge/component_knowledge.json`: Defines isolated hard-facts about the physical domain.

**Later (SQLite):**
- `component_knowledge(id, component_name, properties_list, physics_limits_json, warning_texts, updated_at)`

Purpose: Ensure plans do not hallucinate safe operations on intolerant physical components (e.g. Pump dry-run rules).

### Plan execution storage (State Machine): tables/collections and purpose

**Now (JSON files / In-memory):**
- `data/active_plans.json`: Active plans moving through the state machine.

**Later (SQLite):**
- `plans(id, original_goal, strategy_id, state, steps_json, current_step_index, created_at, updated_at)`
- `plan_events(id, plan_id, event_type, details_json, created_at)`

Purpose: Track the lifecycle of generated plans for auditability, resumption, and replanning.

---as an Execution Graph with `wait_for` properties) using the top-ranked strategy and available skills.
6. Run Dry Run simulation on the drafted plan: propagate `post_conditions` sequentially to verify every step's `pre_conditions` against the current simulated world state.
7. Persist the plan with state `draft` to the Plan execution storage if simulation passes.
8. Return the structured plan or exact Dry Run failures to the LLM so it can self-correct iteratively
Plan Generation flow (`planning.generate_plan`):

1. Validate input payload (`goal`, `constraints`, `capabilities`, `reasoning_context`).
2. Fetch applicable planning strategies matching the goal and domain.
3. Filter strategies based on `constraints` and `priority_policies`.
4. Rank remaining strategies by historical `success_score`.
5. Draft the plan (sequence of steps) using the top-ranked strategy.
6. Run safety and constraint validation on the drafted plan.
7. Persist the plan with state `draft` to the Plan execution storage.
8. Return the structured plan to the LLM for approval or execution.

Plan Update flow (`planning.update_status`):
1. Receive execution outcome for the current step.
2. Advance `current_step_index` or mark step as failed.
3. If failure violates constraints, transition plan to `failed` and invoke replanner fallback.
4. Log event to `plan_events`.

---

## 5) Local vs cloud decision with justification

Decision: **local-first** for MVP.

Decision criteria:
- **Latency:** Interactive agents need instant plan generation and step verification.
- **Governance/security:** Plans specify actions that might modify underlying systems. Local execution ensures tight control over policy enforcement.
- **Cost:** Avoids cloud dependency for deterministic state machine tracking.
- **Complexity:** A local JSON/SQLite store is trivial to integrate with the local Reasoning tool.

---

## 6) Python stack recommendation

- API/MCP layer: `FastAPI`, `pydantic` (strict state machine validation)
- State Tracking: `transitions` or pure Python state machine
- Caching/loading: `orjson`, in-memory Dict for active plans
- Storage migration: `sqlite3` -> `SQLAlchemy`
- Observability: `structlog` for event-sourced audit trails

---

## 7) Risks and mitigations

1. **Infinite Replanning Loops**
   - Mitigation: Strict `max_replans` counter in the plan state model.
2. **Strategy Obsolescence**
   - Mitigation: Versioning for all strategies and tracking success/failure ratios.
3. **Boundary Bleed with Reasoning**
   - Mitigation: Planner must *never* process raw observations. It must explicitly require parsed `reasoning_context`.

---

## 8) Implementation roadmap (phased)

### Phase 1: Planner schema and state machine
- Define MCP contract for plan generation and status tracking.
- Implement the strict state machine (`draft`, `approved`, `executing`, `completed`, `failed`).

### Phase 2: Strategy selection and generation
- Implement tag-based strategy matching.
- Implement policy constraints (e.g. failing a plan draft if it violates a priority).

### Phase 3: Telemetry and replanning
- Add event-sourced execution logging.
- Implement fallback behavior on step failure.
