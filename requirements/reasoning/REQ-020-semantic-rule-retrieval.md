# REQ-020 Semantic Rule Retrieval (Stage 2)

## User Story
As a Host LLM operator,
I want the reasoning tool to find relevant rules even when my query phrasing does not
exactly match the keywords or observation IDs in a rule's trigger,
so that the system works reliably in natural-language and multilingual use cases.

## Background
Stage 1 (deterministic) retrieval requires a precise keyword or observation ID overlap.
This fails when the user's utterance is phrased differently from the rule's stored keywords —
e.g. a German query with umlauts, a synonym, or a paraphrase.  Stage 2 adds a local
vector-similarity search over rule text chunks to close this gap without losing
determinism for existing rules and without requiring a hosted model or internet access.

## Acceptance Criteria

### AC-020-01 — Opt-in activation
- Stage 2 is activated by passing `semantic_search: true` in the `reasoning_analyze_context`
  tool call.  When `false` (default), the pipeline behaves identically to the
  pre-REQ-020 implementation.

### AC-020-02 — Local embedding model
- The server uses `paraphrase-multilingual-MiniLM-L12-v2` from `sentence-transformers`.
- The model runs on CPU with no internet access required after initial download.
- German and English queries must both be supported.

### AC-020-03 — Vector backend
- The vector index is stored locally under
  `<REASON_KNOWLEDGE_DIR>/.semantic_index/` using ChromaDB (persistent, local).
- No external vector database service is required.

### AC-020-04 — Chunk-based indexing
- Each rule is indexed as up to four text chunks: `conditions`, `reasoning`,
  `recommendation`, and `keywords`.
- Domain metadata is stored per chunk so domain filtering can be applied in Stage 2.

### AC-020-05 — Dual-stage merge logic
- A rule is included if it passes Stage 1 (obs_match OR kw_match) **OR** Stage 2
  (semantic cosine similarity ≥ `semantic_min_score`, default 0.75).
- Rules returned by both stages are considered higher-confidence candidates.
- When Stage 2 returns results, catch-all rules (no trigger criteria) are suppressed
  to avoid noise.

### AC-020-06 — Graceful fallback
- If Stage 2 fails (model unavailable, index error, etc.), Stage 1 candidates are
  returned unaffected.  The error is logged but never propagates to the caller.

### AC-020-07 — Cache coherence
- Calling `invalidate_cache()` also clears the semantic index, ensuring Stage 2
  reflects the same rules as Stage 1 after any knowledge update.

### AC-020-08 — Optional dependency isolation
- `sentence-transformers` and `chromadb` are declared under the `[semantic]` extras
  group in `pyproject.toml` and are **not** required for the base installation.
- Importing the embedder module without the extras raises a clear `ImportError` with
  installation instructions.

### AC-020-09 — Response transparency
- When `semantic_search: true`, the response `meta.applied_policies` includes
  `"semantic_retrieval"` and `meta.semantic_search` is `true`.

## Notes
- Query text for Stage 2 is assembled from the caller's `keywords` list and
  observation `observation_id`/`value` pairs.  The caller does not need to provide
  a separate NL string.
- `semantic_min_score` defaults to 0.75 but can be overridden per request for
  stricter or looser matching.
