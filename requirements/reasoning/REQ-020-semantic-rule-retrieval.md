# REQ-020 Semantic Rule Retrieval (Parallel Path)

## User Story
As a Host LLM operator,
I want the reasoning tool to find relevant rules even when my query phrasing does not
exactly match the keywords or observation IDs in a rule's trigger,
so that the system works reliably in natural-language and multilingual use cases.

## Background
Deterministic retrieval requires a precise keyword or observation ID overlap.
This fails when the user's utterance is phrased differently from the rule's stored keywords —
e.g. a German query with umlauts, a synonym, or a paraphrase.  The semantic path adds a
local vector-similarity search over rule text chunks to close this gap without losing
determinism for existing rules and without requiring a hosted model or internet access.

Both paths run in parallel for every request and their results are unioned.  Neither path
gates the other.  A rule found by either path is always included in the candidate set.

## Acceptance Criteria

### AC-020-01 — Always-on parallel retrieval
- The semantic path runs on every `reasoning_analyze_context` call in parallel with
  the deterministic path.  There is no opt-in flag.
- If the `[semantic]` extras are not installed or the index is unavailable, the
  semantic path degrades gracefully and the deterministic path's results are returned
  unaffected.

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
- Domain metadata is stored per chunk so domain filtering can be applied in the
  semantic path.

### AC-020-05 — Parallel union merge logic
- A rule is included if it is found by the deterministic path (obs_match OR kw_match)
  **OR** by the semantic path (cosine similarity ≥ `semantic_min_score`, default **0.45**).
- The threshold default of 0.45 is calibrated for `paraphrase-multilingual-MiniLM-L12-v2`:
  semantically related fact-rules typically score 0.45–0.75 with that model;
  a threshold of 0.75 was empirically found to suppress all valid hits for short fact rules.
- Rules found by both paths carry scores from both and rank higher.
- Catch-all rules (no trigger criteria) are still included via the deterministic path.

### AC-020-06 — Graceful fallback
- If the semantic path fails (model unavailable, index error, etc.), the deterministic
  candidates are returned unaffected.  The error is logged but never propagates to the
  caller.

### AC-020-07 — Cache coherence
- Calling `invalidate_cache()` also clears the semantic index, ensuring both paths
  reflect the same rules after any knowledge update.

### AC-020-08 — Optional dependency isolation
- `sentence-transformers` and `chromadb` are declared under the `[semantic]` extras

### AC-020-09 — Globally unique rule IDs
- Every rule in the knowledge base **must** have a `rule_id` that is unique across
  all JSON files in the deployment's `REASON_KNOWLEDGE_DIR`.
- Duplicate `rule_id` values across files cause two independent failures:
  (a) the semantic index build fails with a `DuplicateIDError` (index stays empty,
      silently disabling semantic retrieval), and
  (b) the filter merge's `rule_by_id` lookup applies last-write-wins semantics,
      returning the wrong rule object for any colliding ID.
- The loader **must** emit a `WARNING` log message listing all duplicate IDs at
  startup when duplicates are detected.
- Recommended convention: prefix rule IDs with a domain or file abbreviation
  (e.g. `CAR-1`, `PRAX-1`, `R-FLEET-WEIGHT-010`).
  group in `pyproject.toml` and are **not** required for the base installation.
- Importing the embedder module without the extras raises a clear `ImportError` with
  installation instructions.

### AC-020-09 — Response transparency
- The response `meta.applied_policies` always includes `"semantic_retrieval"`.

## Notes
- Query text for the semantic path is assembled from the caller's `keywords` list and
  observation `observation_id`/`value` pairs.  The caller does not need to provide
  a separate NL string.
- `semantic_min_score` defaults to 0.75 but can be overridden per request for
  stricter or looser matching.
