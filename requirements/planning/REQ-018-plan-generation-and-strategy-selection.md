# REQ-018 Plan Generation and Strategy Selection

## User Story
As an operations lead,
I want the planner to select a planning strategy based on objective and risk,
so that generated plans are suitable for the current context.

## Acceptance Criteria
- Planner selects strategy from versioned strategy profiles.
- Strategy selection includes objective, risk, and domain profile signals.
- Generated plan includes ordered steps with dependencies.
- Returned plan identifies which strategy version was used.

## Notes
Planning strategies are separate artifacts from reasoning rules.
