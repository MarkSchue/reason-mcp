# REQ-021 Graph Traversal Retrieval

## Status
**Implemented**

## User Story
As a Host LLM operator querying any graph-modelled domain,
I want the reasoning tool to surface entity relationships from a graph database
by traversing connected nodes,
so that a single `reasoning_analyze_context` call returns both rule-based and
graph-relationship context without requiring additional tool calls.

## Background
The graph database models domain entities as a named graph consisting of vertex
collections (nodes) and edge collections (relationships).  The exact collections
and edge topology are fully configurable via `REASON_PRAXIS_VERTEX_SPECS` and
`REASON_PRAXIS_EDGE_SPECS` environment variables — no collection names are
hardcoded in the source.

Each vertex document carries a 384-dim `embedding` vector for semantic node
lookup and a `keywords` array for AQL-based string matching (see REQ-022).
The graph traversal path in `filter.py` runs in addition to the semantic rules path.

## Acceptance Criteria

### AC-021-01 — Semantic node lookup
- The filter's graph path embeds the query text with `paraphrase-multilingual-MiniLM-L12-v2`
  and performs a vector search over all configured vertex collections.
- Only nodes with cosine similarity ≥ `semantic_min_score` (default **0.45**) are traversed.

### AC-021-02 — Keyword node lookup
- In addition to vector search, `keyword_search_nodes()` matches each configured
  vertex collection against the query using AQL string operations on `keywords`,
  `name`, `description`, and `role` fields (see REQ-022).
- Keyword hits are merged with vector hits; the highest score per `node_id` is kept.

### AC-021-03 — 1-hop OUTBOUND traversal
- For each matched vertex node, a 1-hop OUTBOUND AQL traversal is executed through
  the configured named graph, collecting all directly connected neighbour vertices
  and their edges.
- Traversal depth is 1 by default; `traverse_from_node(depth=n)` supports deeper traversal.

### AC-021-04 — Rule-shaped output
- Each graph traversal result is shaped into a rule-like dict with:
  - `rule_id` = the matched node's `node_id`
  - `domain` = `"graph"`
  - `conditions.natural_language` = the node's description plus neighbour descriptions
  - `recommendation.action` = a generated contact / action instruction
  - `_sem_score` = score from the lookup (vector cosine or keyword fixed score)
  - `_source` = `"graph"`
- These dicts pass through the same ranker and compressor as regular rule hits.

### AC-021-05 — Graceful degradation
- If ArangoDB is unavailable or `python-arango` is not installed, the graph path
  returns an empty list.  No error is raised to the caller.
- Graph retrieval failures are logged at WARNING level with the failing `node_id`.

### AC-021-06 — Merged ranking
- Graph results are appended to the merged candidate list returned by `filter_candidates()`.
- The compressor ranks all candidates (semantic rule hits + graph candidates + catch-alls)
  by `_sem_score` before selecting `top_k` for the LLM context.

### AC-021-07 — Observability
- `filter.py` logs `graph_filter` with `query`, `node_hits`, and `candidates` counts.
- `tool.py` includes `graph_hit_count` in step 5 telemetry.

### AC-021-08 — Collection routing via config
- Node collection is inferred from the `node_id` key prefix using
  `REASON_PRAXIS_VERTEX_SPECS` (e.g. `worker_` → `workers` collection).
- No collection or domain names are hardcoded in `arango_client.py`.

## Notes
The graph traversal path is additive and domain-agnostic.  Any domain can be
modelled by creating vertex/edge collections, setting `REASON_PRAXIS_VERTEX_SPECS`
and `REASON_PRAXIS_EDGE_SPECS`, providing seed JSON files under `seeds/`, and
running the seed script.
