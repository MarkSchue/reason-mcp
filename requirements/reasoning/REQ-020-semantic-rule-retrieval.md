# REQ-020 Semantic Rule Retrieval

## User Story
As a Host LLM operator,
I want the reasoning tool to find relevant rules even when my query phrasing does not
exactly match the keywords or observation IDs in a rule's trigger,
so that the system works reliably in natural-language and multilingual use cases.

## Background
Semantic retrieval via local vector similarity is the sole rule-selection mechanism.
A query text is assembled from the caller's `keywords` and observation `observation_id`/`value`
pairs, embedded with `paraphrase-multilingual-MiniLM-L12-v2`, and matched against a local
vector index of rule text chunks.  Catch-all rules (no trigger criteria) are always included
regardless of semantic score so that baseline guidance is never silently dropped.

## Acceptance Criteria

### AC-020-01 — Always-on semantic retrieval
- The semantic path runs on every `reasoning_analyze_context` call.  There is no opt-in flag.
- If the `[semantic]` extras are not installed or the index is unavailable, only catch-all
  rules are returned; no error is raised to the caller.

### AC-020-02 — Local embedding model
- The server uses `paraphrase-multilingual-MiniLM-L12-v2` from `sentence-transformers`.
- The model runs on CPU with no internet access required after initial download.
- German and English queries must both be supported.

### AC-020-03 — Vector backend
- The vector index is stored in ArangoDB (database `reason`, collection `rules`).
- Each rule document carries a 384-dim `embedding` field populated by `seed_arango.py`.
- ArangoDB's `APPROX_NEAR_COSINE` function is used when the cluster version supports it;
  a Python-side cosine similarity fallback is used for older deployments.
- No external vector database service (ChromaDB, Qdrant, etc.) is required.

### AC-020-04 — Chunk-based indexing
- Each rule is indexed as up to four text chunks: `conditions`, `reasoning`,
  `recommendation`, and `keywords`.
- Domain metadata is stored per chunk so domain filtering can be applied in the
  semantic path.

### AC-020-05 — Catch-all rule inclusion
- Rules that define no `trigger.observations`, `trigger.keywords`, and no
  `trigger.context_states` are always included in the candidate set regardless of
  semantic score.
- Domain exclusion is the only filter applied to catch-all rules.

### AC-020-06 — Graceful degradation
- If the semantic path fails (model unavailable, index error, etc.), catch-all rules are
  still returned.  The error is logged but never propagates to the caller.

### AC-020-07 — Cache coherence
- Calling `invalidate_cache()` triggers a re-seed of ArangoDB embeddings on next request,
  ensuring the semantic path reflects the same rules after any knowledge update.

### AC-020-08 — Optional dependency isolation
- `sentence-transformers` is declared under optional extras; if absent, only catch-all rules
  are returned and no error is raised.

### AC-020-09 — Globally unique rule IDs
- Every rule in the knowledge base **must** have a `rule_id` that is unique across
  all JSON files in the deployment's `REASON_KNOWLEDGE_DIR`.
- Duplicate `rule_id` values cause the semantic index build to fail with a
  `DuplicateIDError` (index stays empty, silently disabling semantic retrieval).
- The loader **must** emit a `WARNING` log message listing all duplicate IDs at
  startup when duplicates are detected.
- Recommended convention: prefix rule IDs with a domain or file abbreviation
  (e.g. `CAR-1`, `PRAX-1`, `R-FLEET-WEIGHT-010`).

### AC-020-10 — Response transparency
- The response `meta.applied_policies` always includes `"semantic_retrieval"`.

## Notes
- Query text for the semantic path is assembled from the caller's `keywords` list and
  observation `observation_id`/`value` pairs.  The caller does not need to provide
  a separate NL string.
- `semantic_min_score` defaults to **0.45** and can be overridden per request for
  stricter or looser matching.
