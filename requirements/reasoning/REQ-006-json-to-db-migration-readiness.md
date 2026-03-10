# REQ-006 JSON-to-DB Migration Readiness

## User Story
As a platform architect,
I want the JSON-first model to be migration-ready for SQLite (and later other stores),
so that persistence can scale without redesigning the core contract.

## Acceptance Criteria
- JSON schema fields map cleanly to a relational schema.
- Migration path preserves `rule_id`, version, conditions, and policy semantics.
- Existing contract remains backward-compatible during migration phase.
- Import process from JSON to database is specified and testable.

## Notes
JSON remains an authoring source until DB workflows are stable.
