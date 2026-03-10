# REQ-005 Knowledge Versioning

## User Story
As a knowledge maintainer,
I want rule packs and policy artifacts to be versioned,
so that reasoning outputs are traceable to the exact knowledge state used.

## Acceptance Criteria
- Knowledge artifacts include explicit version metadata.
- Runtime responses expose the active knowledge version.
- The system detects missing or invalid knowledge bundles before evaluation.
- Version changes are auditable in run logs.

## Notes
Versioning is required for reproducibility and controlled updates.
