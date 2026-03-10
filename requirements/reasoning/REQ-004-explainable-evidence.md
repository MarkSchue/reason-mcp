# REQ-004 Explainable Evidence

## User Story
As a reviewer,
I want each reason to include explicit evidence,
so that I can verify why the system produced that conclusion.

## Acceptance Criteria
- Each returned reason includes at least one evidence item.
- Evidence links observed values to evaluated condition logic.
- Response includes confidence per reason.
- If no reason passes threshold, response explains the no-match outcome.

## Notes
Explainability is mandatory for governance and debugging.
