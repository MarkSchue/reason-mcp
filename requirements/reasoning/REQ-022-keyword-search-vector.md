# REQ-022 Keyword Search and Keyword-Vector Search for Graph Nodes

## Status
**Implemented**

## User Story
As a Host LLM operator querying the graph database,
I want each graph node to carry a `keywords` list and a `keywords_embedding` vector
so that the retrieval pipeline can find nodes via both exact/partial string matching
and semantic similarity on the keyword vocabulary,
ensuring that proper-noun and short-phrase queries (e.g. a person's name or a role
title) reliably return the right node even when description cosine similarity is weak.

## Background
Vector embeddings of short proper-noun queries (names, role titles, identifiers)
typically score well below the 0.45 cosine threshold against full-sentence node
descriptions.  Two complementary retrieval paths address this:

1. **AQL keyword search** (`keyword_search_nodes`) — exact and partial string
   matching against a `keywords` array on each node.  Fixed scores of 0.95/0.80.
2. **Keywords vector search** (`keyword_vector_search_nodes`) — embedding of the
   joined keyword string, stored as `keywords_embedding`; cosine similarity against
   the query embedding.  Uses the `graph_kw_vec` ArangoDB vector index.

Both paths run **in addition to** the existing description-vector search
(`vector_search_nodes` / `graph_emb_vec` index, see REQ-021).  All three results
are merged per `node_id` by taking the highest score.

## Data Model
Each node document in any configured vertex collection carries:
```json
{
  "node_id": "<id>",
  "keywords":           ["<term1>", "<term2>", "..."],
  "keywords_embedding": [<384-dim float array>]
}
```
- `keywords` — lowercase strings representing names, roles, identifiers, time labels.
- `keywords_embedding` — 384-dimension embedding of `" ".join(keywords)` produced
  by `paraphrase-multilingual-MiniLM-L12-v2` at seed time.
- Both fields are optional at query time; missing fields degrade gracefully.

## Vector Indexes
Two vector indexes are created per configured vertex collection by
`ensure_graph_vector_indexes()` in `arango_client.py`:

| Index name      | Field               | Purpose                        |
|-----------------|---------------------|-------------------------------|
| `graph_emb_vec` | `embedding`         | Description-based ANN search   |
| `graph_kw_vec`  | `keywords_embedding`| Keywords-based ANN search      |

Both use `metric: cosine`, `dimension: 384`.  `nLists` is computed per collection
as `max(1, min(count, round(15 × √count)))` to avoid Faiss `nx >= k` errors on
small collections.

## AQL Vector Search Pattern
ArangoDB 3.12+ `APPROX_NEAR_COSINE` requires that `SORT` comes immediately after
the `LET score` assignment.  All `FILTER` clauses (including score threshold) must
be placed **after** `SORT … LIMIT`:

```aql
FOR doc IN @@coll
  LET score = APPROX_NEAR_COSINE(doc.<field>, @embedding)
  SORT score DESC
  LIMIT @top_k
  FILTER score >= @min_score
  RETURN {node_id: doc.node_id, score: score}
```

Pre-filtering on other fields before the `LET score` prevents the query optimizer
from selecting the vector index.

## Acceptance Criteria

### AC-022-01 — Keyword Fields on Nodes
- Each node carries a `keywords` array (lowercase strings) and a
  `keywords_embedding` (384-dim float list).
- Seed files (`seeds/nodes/*.json`) include explicit `keywords` for all
  authoritative nodes.
- The seed script (`scripts/seed_praxis_graph.py`) auto-generates `keywords` from
  `name`, `role`, `phone`, `email`, `days`, `start`, `end` when absent.
- `keywords_embedding` is always computed as `embed_text(" ".join(keywords))`.
- Explicit `keywords` in the seed file always take precedence over auto-generation.

### AC-022-02 — AQL Keyword String Search
- `keyword_search_nodes()` in `arango_client.py` issues one AQL query per vertex
  collection matching a node when **any** hold:
  - The `keywords` array contains an entry that equals, contains, or is contained
    by the normalised query string.
  - The `keywords` array contains an entry matching any individual query token.
  - The `name`, `description`, or `role` field matches the query or any token
    (fallback for nodes without `keywords`).
- Score mapping:
  - **0.95** — exact name match, name ⊂ query, or keyword == query / keyword ⊂ query.
  - **0.80** — token-level partial match on any field or keyword.
- Missing `keywords` field handled in AQL: `doc.keywords != null ? doc.keywords : []`.

### AC-022-03 — Keywords Vector Search
- `keyword_vector_search_nodes()` in `arango_client.py` runs `APPROX_NEAR_COSINE`
  on `doc.keywords_embedding` using the `graph_kw_vec` index.
- Falls back to Python-side cosine when the native query fails (e.g. missing index).
- Logs `keyword_vector_search_nodes` with `hits`, `collections`, and `node_type`.

### AC-022-04 — Vector Indexes
- `ensure_graph_vector_indexes()` creates `graph_emb_vec` (on `embedding`) and
  `graph_kw_vec` (on `keywords_embedding`) on every configured vertex collection.
- Idempotent: skips creation if the named index already exists.
- Uses per-collection `coll.count()` to compute `nLists`, preventing Faiss errors
  on small collections.
- Called by the seed script after all node upserts.

### AC-022-05 — Three-Path Merge
- `_graph_candidates()` in `filter.py` runs all three paths for every query:
  1. `vector_search_nodes()` — description embedding (`graph_emb_vec`)
  2. `keyword_vector_search_nodes()` — keywords embedding (`graph_kw_vec`)
  3. `keyword_search_nodes()` — AQL string match
- Results are merged per `node_id`: the highest score from any path is kept.
- The merged list is trimmed to `top_k` and processed identically to pure vector hits.

### AC-022-06 — Graceful Degradation
- Each path that raises an exception causes a WARNING log and an empty result;
  the other paths continue.
- Missing `keywords` or `keywords_embedding` fields on a node do not cause errors.

### AC-022-07 — Observability
- Each retrieval function logs at INFO level with `hits`, relevant collection/query
  info, and `node_type`.

### AC-022-08 — Seed Idempotency
- Re-running the seed script overwrites `keywords`, `keywords_embedding`, and both
  vector indexes without duplicating entries, consistent with `overwrite_mode="replace"`.

## Notes
- The `keywords` field is complementary to the `embedding` field; both live on
  the same node document.
- Keyword search is purely AQL string operations — no extra index is required
  beyond the existing `idx_node_id` persistent index.
- Adding a new domain requires no code changes: seed the vertex collections with
  nodes that have `keywords` and the retrieval pipeline picks them up automatically.
