# REQ-013 Semantic Match Explainability

## User Story
As a reviewer,
I want visibility into why a non-exact term matched a stored concept,
so that semantic decisions remain auditable and trustworthy.

## Acceptance Criteria
- Responses can include semantic match evidence for key mapped terms.
- The system can expose which normalized concept was used for matching.
- Semantic confidence is available separately from rule confidence when requested.
- Audit logs preserve term-mapping traces for post-hoc inspection.

## Notes
Example trace: input "vehicle" mapped to concept "car" for rule candidate selection.
