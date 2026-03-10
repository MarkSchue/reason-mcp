# REQ-025 Dry Run Validation and MCP Self-Correction Loop

**User Story:**
As a host LLM agent,
I want to test (dry-run) a drafted plan via a specific MCP tool before committing to its execution,
so that I can receive exact pre-condition or policy violation feedback and iteratively self-correct my plan in a ReAct loop.

**Acceptance Criteria:**
1. **Simulation Endpoint:** An explicit `simulate_and_validate_plan` MCP endpoint exists to perform a dry run.
2. **Actionable Feedback:** If simulation fails, the endpoint returns exact, localized feedback (e.g., "Step 2 violates pre-condition: pressure must be < 2.0").
3. **ReAct Compatibility:** The feedback must concisely guide the calling LLM to revise the plan, allowing it to insert prerequisite steps (e.g., stopping a machine before opening a valve).