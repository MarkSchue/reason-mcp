# REQ-006 JSON-to-ArangoDB Migration Readiness

## User Story
As a platform architect,
I want the JSON-first authoring model to map cleanly onto the ArangoDB runtime store,
so that rule development stays simple while persistence and retrieval scale without
redesigning the core contract.

## Status
**Implemented** — ArangoDB is the live runtime store for both the rules DB (`reason`)
and the praxis domain graph DB (`praxis`).  JSON files remain the canonical authoring
source; seed scripts embed and upsert them into ArangoDB on each run.

## Acceptance Criteria
- JSON schema fields map cleanly to ArangoDB document fields and vertex/edge collections.
- Each rule document carries a 384-dim `embedding` array enabling `APPROX_NEAR_COSINE`
  vector search in ArangoDB.
- Migration path (JSON → ArangoDB) is automated via idempotent seed scripts:
  - `scripts/seed_arango.py` — upserts rules with embeddings into the `reason` database.
  - `scripts/seed_praxis_graph.py` — upserts Worker, WorkingHours nodes and
    arbeitet/vertritt edges with embeddings into the `praxis` database.
- Seed scripts are idempotent: re-running them does not create duplicates.
- Existing MCP contract (`reasoning_analyze_context`) remains backward-compatible with
  the new ArangoDB backend; callers observe no change in request/response schema.
- ArangoDB connection parameters are fully configurable via `REASON_ARANGO_*` and
  `REASON_PRAXIS_*` environment variables (see `config.py`).

## Notes
JSON files remain the authoring source; ArangoDB is the runtime store.  Any change to
a JSON knowledge or seed file requires a re-run of the corresponding seed script to
propagate the change to ArangoDB.
