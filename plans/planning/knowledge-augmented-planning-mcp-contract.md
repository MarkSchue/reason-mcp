# Planning MCP Contract (`planning.generate_plan`, `planning.simulate_and_validate`, `planning.update_status`)

## Purpose
Define the MCP contract for the Planner tool. The planner relies exclusively on goals and synthesized constraints (such as those output by the Reasoning MCP) and maintains a strict state machine boundary. Includes a self-correction simulation loop for agent dry runs.

---

## 1) Tool definitions

### Tool 1: `planning.generate_plan`
- **Goal:** Draft an executable plan based on a goal, constraints, and known capabilities.
- **Output:** A structured plan object in `draft` state structured as an Execution Graph.

### Tool 2: `planning.simulate_and_validate`
- **Goal:** Run a step-by-step Dry Run of a drafted plan against physical `component_knowledge` and `pre_conditions`.
- **Output:** `valid: true` or precise feedback on exactly which condition failed in which step, allowing the host LLM to loop and self-correct.

### Tool 3: `planning.update_status`
- **Goal:** Update the execution state of an active plan step.
- **Output:** The next steps, state transition, or a replanning schema if a failure occurred.

---

## 2) Request Schemas

### `planning.generate_plan` Request
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "kar.planning.generate_plan.request.v1",
  "type": "object",
  "required": ["goal", "constraints"],
  "properties": {
    "goal": {
      "type": "string",
      "description": "The high-level objective to achieve."
    },
    "reasoning_context": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Insights/rule_ids provided by the Reasoning MCP."
    },
    "constraints": {
      "type": "object",
      "properties": {
        "max_duration_ms": { "type": "integer" },
        "safety_level": { "type": "string", "enum": ["standard", "strict"] }
      }
    }
  }
}
```

### `planning.update_status` Request
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "kar.planning.update_status.request.v1",
  "type": "object",
  "required": ["plan_id", "step_id", "outcome"],
  "properties": {
    "plan_id": { "type": "string" },
    "step_id": { "type": "string" },
    "outcome": {
      "type": "string",
      "enum": ["success", "failure"]
    },
    "error_details": { "type": "string" }
  }
}
```

### `planning.simulate_and_validate` Request
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "kar.planning.simulate_and_validate.request.v1",
  "type": "object",
  "required": ["plan_id"],
  "properties": {
    "plan_id": { "type": "string", "execution_graph"],
  "properties": {
    "plan_id": { "type": "string" },
    "state": { "type": "string", "enum": ["draft", "approved", "failed"] },
    "strategy_used": { "type": "string" },
    "execution_graph": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step_id", "action"],
        "properties": {
          "step_id": { "type": "string" },
          "action": { "type": "string" },
          "wait_for": { 
            "type": "array", 
            "items": { "type": "string" },
            "description": "step_ids that must complete before this step"
         
  "type": "object",
  "required": ["plan_id", "state", "steps"],
  "properties": {
    "plan_id": { "type": "string" },
    "state": { "type": "string", "enum": ["draft", "approved", "failed"] },
    "strategy_used": { "type": "string" },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step_id", "action", "expected_outcome"],
        "properties": {
          "step_id": { "type": "string" },
          "action": { "type": "string" },
          "expected_outcome": { "type": "string" }
        }
      }
    }
  }
}
```

### `planning.simulate_and_validate` Response
```json
{
  "type": "object",
  "required": ["valid"],
  "properties": {
    "valid": { "type": "boolean" },
    "error_step_id": { "type": "string" },
    "violation_reason": { 
      "type": "string",
      "description": "E.g., 'Pre_condition [pressure < 2.0] failed. Current simulated pressure is 6.5.'"
    },
    "suggested_mitigation": { "type": "string" }
  }
}
```

### `planning.update_status` Response
```json
{
  "type": "object",
  "required": ["plan_id", "current_state"],
  "properties": {
    "plan_id": { "type": "string" },
    "current_state": { "type": "string", "enum": ["executing", "completed", "failed", "replanning"] },
    "next_step_id": { "type": "string" },
    "message": { "type": "string" }
  }
}
```