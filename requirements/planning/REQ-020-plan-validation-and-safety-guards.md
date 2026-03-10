# REQ-020 Plan Validation and Safety Guards

## User Story
As a governance owner,
I want plans to be validated against policy and safety checks before execution,
so that unsafe or non-compliant plans are blocked.

## Acceptance Criteria
- Pre-execution validation is mandatory for each generated or updated plan.
- Policy violations return structured rejection reasons.
- Planner supports configurable hard-stop conditions.
- Validation outcome is recorded in plan audit history.

## Notes
Safety checks are required regardless of domain.
