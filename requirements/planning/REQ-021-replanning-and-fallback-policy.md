# REQ-021 Replanning and Fallback Policy

## User Story
As a planner user,
I want automatic replanning and fallback behavior when assumptions fail,
so that execution can continue safely under changing conditions.

## Acceptance Criteria
- Replanning triggers are defined (for example blocked step, failed dependency, changed constraint).
- Planner can produce a revised plan linked to previous plan version.
- Fallback policy supports degraded but safe continuation.
- Replanning events are logged with cause and outcome.

## Notes
Replanning is essential for real-world dynamic environments.
