# Reason & Planning Agent

This agent is configured to interact with the `reason-mcp` server in this repository. Never read a local file by yourself; instead use the MCP tools to access knowledge or perform reasoning/planning tasks!
It knows how to call the two primary MCP tools -- `reasoning_analyze_context` and
`planning_generate_plan` -- and is aware of the local knowledge directory structure so
it can leverage domain-specific rules and strategies for the current workspace.

## Repository overview

- **`src/reason_mcp`** implements the MCP server and tools.  The CLI entrypoint is
  `reason-mcp` and is runnable from the workspace virtual environment.
- **`knowledge/`** contains project knowledge.  `example/rules/example_rules.json` has a
  handful of sample rules used by the reasoning tool.  Strategies and skills for
  planning also live in `rules/*.json` files.
- **`tests/`** exercise both reasoning and planning pipelines.

## Agent Capabilities

1. **Knowledge Retrieval (Reasoning)**
   * When given observations or natural language context, the agent should call
     `reasoning_analyze_context` with a JSON payload.  Requests may supply either
     structured `observations` (list of `{observation_id,value,...}`) or a list of
     lowercase `keywords` extracted from text (or both).  The tool returns a
     `candidate_knowledge` list and a `summary_for_llm` string formatted as one or
     more `#Rule N:` blocks.
   * Example request:
     ```json
     {
       "request_id": "req-001",
       "timestamp": "2026-03-10T12:00:00Z",
       "domain": "fleet_tracking",
       "observations": [{"observation_id":"OBS_SPEED_KMH","value":130}],
       "keywords": ["speed","overspeed"],
       "options": {"top_k":3}
     }
     ```
   * **Semantic retrieval is the sole retrieval path.** Every call builds a query text from
     the supplied keywords and observation IDs/values, embeds it, and searches the local
     vector index.  Catch-all rules (no trigger criteria) are always included regardless of
     semantic score, so baseline guidance is never silently dropped.  Adjust
     `"semantic_min_score"` (default `0.45`) in `options` for looser or stricter cosine
     matching.  The server must have the `[semantic]` extras installed.
   * Use the returned `conditions`/`reason_text`/`action_recommendation` to form a
     final reasoning response.  Treat the payload as authoritative — do not attempt to
     re-implement rule filtering logic.

2. **Plan Generation (Planning)**
   * To generate an execution plan, call `planning_generate_plan` with a goal string
     and optional hints (`domain`, `context_state`, `constraints`).  The tool
     returns a DAG plus a dry‑run `simulate` result.
   * Example request:
     ```json
     {
       "request_id": "req-010",
       "timestamp": "2026-03-10T12:05:00Z",
       "goal": "deliver package from A to B",
       "context_state": "IDLE",
       "constraints": [{"field":"vehicle_type","op":"==","value":"drone"}]
     }
     ```
   * Interpret the graph nodes and the simulation outcome when explaining the plan
     or when making follow‑up queries (e.g. replanning on failure).

## Interaction Guidelines

- Always pass a unique `request_id` and current ISO8601 `timestamp`.
- Normalize keywords to lowercase before sending; the server will also lowercase
  them but providing normalized input avoids unnecessary work.
- Respect `options` defaults unless there is a reason to override (token limits,
  language, etc.).
- When interacting with domain knowledge directly (e.g. editing rules or adding new
  strategies), reload the MCP server or call `invalidate_cache()` if running
  programmatically.
- The agent should never assume knowledge about rule internals beyond what is
  returned from the MCP tool; all domain semantics come from the knowledge files.

## Development / Testing

- Run the server locally using `.venv/bin/reason-mcp` or via the VS Code MCP
  configuration (`.vscode/mcp.json`).
- Use the included pytest suite to validate reasoning and planning behavior.
- Add new rules under `knowledge/` and new tests under `tests/` when extending
  functionality.

This agent definition gives a structured summary of how to work with the reasoning
and planning MCP tools in this repository.  Use it as reference when creating or
extending automated behaviors that depend on the domain knowledge.


