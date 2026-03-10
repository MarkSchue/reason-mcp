# REQ-019 Keyword-Based Semantic Rule Retrieval

## User Story
As a Host LLM operator,
I want to retrieve relevant rules by supplying a list of lowercase keywords extracted from a natural-language query,
so that the reasoning tool can surface applicable rules even when no structured observation IDs are available.

## Background
A Host LLM receiving a natural-language prompt such as "I have a car that weighs 5000 kg" extracts keywords
like `["car", "weight"]` and passes them to `reasoning_analyze_context`.  The tool matches these keywords
against `trigger.keywords` stored on each rule, enabling discovery without structured sensor data.

## Acceptance Criteria

### AC-019-01 — Rule-side keyword declaration
- Each rule **should** define a `trigger.keywords` array of lowercase strings.
- Keywords may include synonyms, units, and domain terms (e.g. `["car", "vehicle", "fleet", "kg"]`).
- `trigger.keywords` and `trigger.observations` are independent; a rule may have both, one, or neither.

### AC-019-02 — Request-side keyword parameter
- `reasoning_analyze_context` accepts an optional `keywords: list[str] | None` parameter.
- The server normalizes input keywords to lowercase before matching.

### AC-019-03 — OR-logic filter
- A rule is a candidate if:
  - `obs_match`: the request observation IDs overlap with `trigger.observations`, **OR**
  - `kw_match`: the request keywords overlap with a rule's `trigger.keywords`.
- Rules that define neither `trigger.observations` nor `trigger.keywords` are treated as catch-all candidates.
- Domain and `context_state` exclusion filters apply before the OR-logic test.

### AC-019-04 — Summary rendering
- `summary_for_llm` in the response is rendered as `#Rule N:` formatted blocks:
  ```
  #Rule 1: <conditions.natural_language>
  **Reason:** <possible_causes joined by ", ">
  **Recommendation:** <recommendation.action>
  ```
- An empty string is returned when no rules matched.

### AC-019-05 — Backward compatibility
- Existing rules without `trigger.keywords` continue to be matched via `trigger.observations` only.
- Existing callers that omit `keywords` from the request are unaffected.

## Notes
- Keyword extraction from NL queries is the responsibility of the Host LLM, not the MCP server.
- `trigger.keywords` is for coarse-grained discovery; the Host LLM performs fine-grained reasoning over the returned rule conditions.
