```markdown
# REQ-021 Graph Traversal Retrieval

## User Story
As a Host LLM operator querying the praxis domain,
I want the reasoning tool to surface entity relationships (working hours, substitutes)
from a graph database by traversing connected nodes,
so that a single `reasoning_analyze_context` call returns both rule-based and
graph-relationship context without requiring additional tool calls.

## Background
The `praxis` ArangoDB database models domain entities as a named graph:
- **Vertex collections:** `workers` (Worker nodes), `working_hours` (WorkingHours nodes)
- **Edge collections:** `arbeitet` (Worker → WorkingHours), `vertritt` (Worker → Worker,
  substitution)
- **Named graph:** `praxis_graph`

Each vertex document carries a 384-dim `embedding` vector for semantic node lookup.
The graph traversal path runs in parallel with the semantic rules path in `filter.py`.

## Acceptance Criteria

### AC-021-01 — Semantic node lookup
- The filter's graph path embeds the query text with `paraphrase-multilingual-MiniLM-L12-v2`
  and performs a vector search over both vertex collections (`workers`, `working_hours`).
- Only nodes with cosine similarity ≥ `semantic_min_score` (default **0.45**) are traversed.

### AC-021-02 — 1-hop OUTBOUND traversal
- For each matched vertex node, a 1-hop OUTBOUND AQL traversal is executed through
  `praxis_graph`, collecting all directly connected neighbour vertices and their edges.
- Traversal depth is 1 by default; `traverse_from_node(depth=n)` supports deeper traversal.

### AC-021-03 — Rule-shaped output
- Each graph traversal result is shaped into a rule-like dict with:
  - `rule_id` = the matched node's `node_id`
  - `domain` = `"praxis"`
  - `conditions.natural_language` = the node's description plus neighbours
  - `recommendation.action` = contact instruction for Worker nodes
  - `_sem_score` = cosine score from node lookup
  - `_source` = `"graph"`
- These dicts pass through the same ranker and compressor as regular rule hits.

### AC-021-04 — Graceful degradation
- If ArangoDB is unavailable or `python-arango` is not installed, the graph path
  returns an empty list.  No error is raised to the caller; the semantic rules path
  and catch-all rules still function normally.
- Graph retrieval failures are logged at WARNING level with the failing `node_id`.

### AC-021-05 — Merged ranking
- Graph results are appended to the merged candidate list returned by `filter_candidates()`.
- The compressor ranks all candidates (semantic rule hits + graph candidates + catch-alls)
  by `_sem_score` before selecting `top_k` for the LLM context.

### AC-021-06 — Observability
- `filter.py` logs `graph_filter` with `query`, `node_hits`, and `candidates` counts.
- `tool.py` includes `graph_hit_count` in step 5 telemetry and adds `"graph_traversal"`
  to `applied_policies` in the response.

### AC-021-07 — Key prefix routing
- Node collection is inferred from the document key prefix:
  - `worker_*` → `workers` collection
  - `hours_*` → `working_hours` collection
- This routing is implemented in `_vertex_coll_for_node_id()` in `arango_client.py`.

## Notes
The graph traversal path is additive — it does not replace the semantic rule path.
New graph domains (beyond praxis) can be added by creating new vertex/edge collections,
updating `config.py`, and extending `_graph_candidates()` in `filter.py`.
```
