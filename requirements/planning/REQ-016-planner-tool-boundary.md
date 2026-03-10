# REQ-016 Planner Tool Boundary

## User Story
As a platform architect,
I want planning to be implemented as a dedicated MCP tool separated from reasoning,
so that each tool has clear responsibility and can be evolved independently.

## Acceptance Criteria
- Planning is exposed through a dedicated planner MCP endpoint separate from reasoning.
- Reasoning outputs can be consumed by planner as input, but planner does not reuse reasoning endpoint directly for plan generation.
- Tool responsibilities are documented (reasoning identifies reasons; planner creates and maintains plans).
- Failure in one tool does not prevent the other tool from operating in degraded mode.

## Notes
This requirement formalizes the two-tool architecture.
