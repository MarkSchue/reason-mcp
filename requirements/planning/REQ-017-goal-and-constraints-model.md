# REQ-017 Goal and Constraints Model

## User Story
As a planner client,
I want to provide goals and constraints in a structured model,
so that plan generation is consistent and policy-aware across domains.

## Acceptance Criteria
- Planner input supports explicit goal, constraints, priorities, and optional deadline.
- Constraints support hard and soft categories.
- Missing critical planning fields return structured validation errors.
- Input model remains domain-agnostic and reusable across contexts.

## Notes
This model is independent of observation schema used by reasoning.
