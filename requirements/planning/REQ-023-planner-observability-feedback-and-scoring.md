# REQ-023 Planner Observability, Feedback, and Scoring

## User Story
As a reliability engineer,
I want planner telemetry and outcome feedback captured,
so that planning quality can be measured and improved over time.

## Acceptance Criteria
- Planner logs include request id, plan id, strategy version, and latency.
- Execution outcomes can be linked to plan versions and steps.
- Feedback signals support plan quality scoring and regression detection.
- Planner KPIs include success rate, replan rate, and time-to-completion.

## Notes
This requirement is planner-specific and separate from reasoning telemetry.
