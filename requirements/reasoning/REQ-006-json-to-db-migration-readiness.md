# REQ-006 JSON-to-ArangoDB Migration Readiness

## User Story
As a platform architect,
I want the JSON-first authoring model to map cleanly onto the ArangoDB runtime store,
so that rule development stays simple while persistence and retrieval scale without
redesigning the core contract.

## Status
**Implemented** — ArangoDB is the live runtime store for both the rules database
(`REASON_ARANGO_DB`, default `reason`) and each configured graph database
(`REASON_PRAXIS_DB`, default `praxis`).  JSON files remain the canonical authoring
source; seed scripts embed and upsert them into ArangoDB on each run.

## Acceptance Criteria
- JSON schema fields map cleanly to ArangoDB document fields and vertex/edge collections.
- Each rule document carries a 384-dim `embedding` array enabling `APPROX_NEAR_COSINE`
  vector search in ArangoDB.
- Each graph node document carries:
  - A 384-dim `embedding` array for vector similarity search.
  - A `keywords` array of lowercase strings for AQL-based keyword search (see REQ-022).
- Migration path (JSON → ArangoDB) is automated via idempotent seed scripts:
  - `scripts/seed_arango.py` — upserts rules with embeddings into the rules database.
  - `scripts/seed_praxis_graph.py` — upserts graph nodes (with embeddings and keywords)
    and edges into the configured graph database.  Node definitions live under
    `seeds/nodes/*.json`; edge definitions under `seeds/edges/*.json`.
- Seed scripts are idempotent: re-running them does not create duplicates.
- Existing MCP contract (`reasoning_analyze_context`) remains backward-compatible with
  the new ArangoDB backend; callers observe no change in request/response schema.
- ArangoDB connection parameters are fully configurable via `REASON_ARANGO_*` and
  `REASON_PRAXIS_*` environment variables (see `config.py`).
- The vertex/edge schema (collection names, key prefixes, edge topology) is driven
  entirely by `REASON_PRAXIS_VERTEX_SPECS` / `REASON_PRAXIS_EDGE_SPECS`; no
  domain-specific names are hardcoded in library code.

## Notes
JSON files remain the authoring source; ArangoDB is the runtime store.  Any change to
a knowledge or seed JSON file requires a re-run of the corresponding seed script to
propagate the change to ArangoDB.
