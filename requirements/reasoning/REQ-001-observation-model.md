# REQ-001 Observation Model

## User Story
As a domain expert,
I want the tool to accept normalized observations instead of domain-specific field types,
so that the same reasoning architecture works across production, health, chemistry, and other domains.

## Acceptance Criteria
- Input payload supports an `observations` array with generic fields (`observation_id`, `value`, optional metadata).
- The contract does not require sensor-specific or machine-specific fields.
- Observations can contain numeric, categorical, or boolean values.
- The same payload shape is valid across at least two distinct domains without schema changes.

## Notes
This requirement establishes the domain-agnostic foundation.
