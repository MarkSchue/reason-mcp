# REQ-019 Plan State Machine and Persistence

## User Story
As a planner operator,
I want every plan to have a durable lifecycle state,
so that execution progress and recovery can be managed reliably.

## Acceptance Criteria
- Plan lifecycle includes at least: `draft`, `approved`, `executing`, `blocked`, `completed`, `failed`.
- State transitions are validated and auditable.
- Plan state is persisted and recoverable after restart.
- Transition history records actor, timestamp, and reason.

## Notes
State durability is required for long-running workflows.
