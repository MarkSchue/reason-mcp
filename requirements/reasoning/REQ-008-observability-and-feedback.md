# REQ-008 Observability and Feedback

## User Story
As a reliability engineer,
I want full reasoning telemetry and feedback capture,
so that we can improve reasoning quality and detect regressions.

## Acceptance Criteria
- Each run logs request id, trace id, latency, candidate count, and matched count.
- Logs include top returned rule identifiers and applied policy versions.
- Response-size metrics are captured for context-window optimization.
- Feedback signals (for example resolved/false_positive/ignored) can be linked to runs.

## Notes
Telemetry is a prerequisite for continuous reasoning improvement.
