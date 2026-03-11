# Knowledge-Augmented Reasoning Architecture Plan (Domain-Agnostic MVP)

## 1) Recommended architecture (1-2 paragraphs)

Primary recommendation: build a **local-first, semantic MCP reasoning service** that uses domain knowledge JSON rule packs as the authoritative source and treats all runtime inputs as **observations**. The system should support broad domain portability by avoiding domain-specific field assumptions and operating on normalized observation objects, context attributes, and policy-driven reasoning strategies.

For MVP, use one MCP endpoint (`reasoning.analyze_context`) guided by the **"Lean Context Injection"** principle. The system employs strict relevance controls to ensure the prompt window remains as lean as possible—it returns only the **top-k ranked candidate rules** relevant to the given observations. Any physical constants or domain-specific limits are embedded directly within rule conditions and are therefore included automatically. The tool injects *what is really needed, but nothing more*. Keep planning as a separate concern in a dedicated MCP tool. Store reasoning runs immediately so execution logs can be correlated by external tools. JSON files remain the authoring source; ArangoDB is the runtime store — populated by idempotent seed scripts that embed and upsert both rules and graph nodes.

---

## 2) Component diagram in words

Request path (reasoning-first):

1. **Host LLM / Agent** sends context (observations, context attributes, task metadata) to MCP.
2. **MCP API Layer** validates schema and applies safety limits (max observations, max tokens, timeout).
3. **Context Input Pruner (Zero-Value Pruning)** mathematically drops observations within nominal baselines (standard deviation/thresholds) to reduce background noise and save context tokens.
4. **Knowledge Loader** loads and caches JSON rule packs.
5. **Candidate Filter** retrieves candidates via two parallel paths:
   - *Semantic path*: a query text is built from the caller's keywords and observation IDs/values,
     embedded with `paraphrase-multilingual-MiniLM-L12-v2`, and matched against the ArangoDB
     vector index (rules collection, `APPROX_NEAR_COSINE`).
   - *Graph traversal path*: the same query embedding is used to search the praxis node
     collections semantically; each matched node is traversed 1 hop OUTBOUND through the
     `praxis_graph` named graph, collecting linked WorkingHours and substitute Worker nodes.
     Results are shaped into rule-like dicts for uniform ranking.
   Catch-all rules (no trigger criteria) are always included regardless of semantic score.
6. **Context & Evidence Builder** bundles the pruned observations and retrieved candidate rules into an injected prompt payload.  Any physical constants and domain facts are already embedded in rule conditions.
7. **Ranker** scores candidates by semantic relevance, severity, freshness, and trigger confidence to fit context windows.
8. **Relevance Compressor** applies deduplication and "Lean Context Injection" rules: strips metadata tags from JSON returned to the LLM, thereby keeping context maximally lean.
9. **Response Composer** returns the bundled domain rules to the Host LLM.
10. **Run Logger** stores telemetry for the retrieved knowledge.

**(Crucial Architecture Boundary):**
- The **Tool** only retrieves and assembles domain-specific rules (which embed any required facts as conditions).
- The **Host LLM** ingests this constructed context to evaluate the rules, derive factual consistency from embedded condition values, and execute the actual reasoning/root-cause analysis.

---

## 3) Storage design (tables/collections + why)

### Knowledge storage: tables/collections and purpose

**Authoring source (JSON files):**
- `knowledge/rules/*.json`: domain rule packs.  Rule conditions embed physical constants and domain facts directly as `exact` predicates (with literal values) or `natural_language` text.
- `knowledge/taxonomy/context_terms.json`: normalized aliases, observation types, and context terms
- `seeds/nodes/*.json`: graph node definitions (workers, working hours, …)
- `seeds/edges/*.json`: graph edge definitions (arbeitet, vertritt, …)

**Runtime store (ArangoDB `reason` database):**
- `rules` collection: rule documents with 384-dim `embedding` vectors for `APPROX_NEAR_COSINE` search
- `rule_relations` edge collection: rule-to-rule relationship edges

**Graph store (ArangoDB `praxis` database):**
- `workers` vertex collection: Worker nodes with embeddings
- `working_hours` vertex collection: WorkingHours nodes with embeddings
- `arbeitet` edge collection: Worker → WorkingHours
- `vertritt` edge collection: Worker → Worker (substitution)
- `praxis_graph` named graph: covers both edge definitions

Purpose: store canonical reasoning rules and domain entity graphs; support both vector
similarity search and AQL graph traversal in a single database engine.

### Capabilities storage: tables/collections and purpose

**Now (JSON file):**
- `capabilities/capabilities.json` with supported observation types, operators, and limits

**Later (ArangoDB, if needed at scale):**
- `capabilities` vertex collection: `(id, name, version, preconditions_json, limits_json, owner, status, updated_at)`

Purpose: declare what the tool can evaluate and under which constraints.

### Concrete schema example (MVP JSON rule)

```json
{
  "rule_id": "R-GEN-ANOMALY-001",
  "domain": "generic",
  "business_intent": "When we are in production mode, check for logical inconsistencies regarding weight, or if pressure goes out of bounds.",
  "trigger": {
    "observations": ["OBS_PRESSURE", "OBS_WEIGHT", "OBS_CAR_COUNT"],
    "context_states": ["PRODUCTION"]
  },
  "conditions": {
    "exact": [
      {"left": "context_state", "op": "==", "right": "PRODUCTION"},
      {"left": "OBS_PRESSURE", "op": ">=", "right": 8.0},
      {"left": "OBS_PRESSURE", "op": "<=", "right": 10.0}
    ],
    "natural_language": "Pressure must stay between 8.0 and 10.0 atm.  A standard car weighs 1000 kg — three cars should weigh approximately 3000 kg total."
  },
  "reasoning": {
    "template": "Observation violated rule bounds: {evaluation_rationale}",
    "possible_causes": ["sensor drift", "load configuration error"],
    "confidence_prior": 0.85
  },
  "recommendation": {
    "action": "Review recent changes and component calibration.",
    "urgency": "high"
  },
  "scoring": {
    "severity": 4,
    "specificity": 0.90
  },
  "tags": ["anomaly", "hybrid-check"],
  "version": "1.2.0",
  "active": true
}
```

---

## 4) Knowledge Retrieval & Context Assembly Flow

To support the Host LLM evaluating the two variations of rule conditions (Exact and NL), the pipeline behaves as follows:

1. Validate input payload (`timestamp`, `observations`, optional `domain`, optional context attributes).
2. Apply **Zero-Value Pruning** to strip out nominal, non-anomalous background observations to radically reduce noise and token usage.
3. Normalize observation keys/units and map aliases through taxonomy.
4. Build candidate rule set via semantic vector search (rules collection in ArangoDB) AND, when a
   graph domain is active, a parallel AQL graph traversal (praxis DB: `workers`, `working_hours`,
   `arbeitet`, `vertritt`).  Graph node results are shaped as rule-like dicts and merged with
   semantic hits before ranking.
5. **Rank & Compress Relevant Knowledge (Lean Context Injection):** Score all candidates (semantic
   rule hits + graph node candidates + catch-all rules) by semantic alignment, severity, and context
   relevance to select the `top_k`. Strip out any internal metadata (tags, backend IDs, schema
   versions, `_source`, `_sem_score`) before payload generation.
6. Compose a highly lean, token-optimized JSON payload combining:
   - Only the pruned, active anomalous observations (nominal background noise stripped).
   - The lean Domain Rules (including `exact` and `natural_language` conditions with any embedded facts, minus developer metadata).
7. Deliver bundle to the Host LLM.
8. Log the retrieval run for later tuning.

**(Execution Handoff):** The **Host LLM** takes this bundled response and acts as the Reasoner:
   - Evaluates `conditions.exact` logical boundaries (including any numeric fact values embedded as `right` operands).
   - Parses the `natural_language` rules against the pruned anomalies.
   - Merges mathematical checks with logical constraints to generate the root-cause reasoning.

---

## 5) End-to-End Example: "The Red Convertible" Contradiction

To illustrate the lean retrieval and LLM reasoning handoff, consider a simple, proprietary business rule that no LLM could know from its training data.

**1. The Domain Knowledge (Stored as JSON in the tool):**
```json
{
  "rule_id": "R-VEHICLE-005",
  "domain": "fleet_tracking",
  "trigger": {"observations": ["OBS_VEHICLE_SEEN"]},
  "conditions": {
    "natural_language": "A red car is always a convertible."
  },
  "tags": ["metadata_to_be_stripped"]
}
```

**2. The Inbound Context (Host LLM calling the MCP Tool):**
```json
{
  "observations": [
    {"observation_id": "OBS_VEHICLE_SEEN", "value": "I have seen a red van", "type": "sighting"}
  ]
}
```

**3. The Tool's Retrieval & Compression Execution:**
- **Pruning:** It sees `OBS_VEHICLE_SEEN`, which is an anomaly/target event. No pruning.
- **Filtering:** It matches the trigger and retrieves `R-VEHICLE-005`.
- **Lean Injection:** It strips internal metadata (`tags`, `domain`) and formats a lean payload.

**4. The Returned Lean Payload (Back to Host LLM):**
```json
{
  "candidate_knowledge": [
    {
      "rule_id": "R-VEHICLE-005",
      "conditions": {"natural_language": "A red car is always a convertible."}
    }
  ],
  "summary_for_llm": "Found 1 relevant domain rule(s) matching your observations. Apply the provided conditions to reason about your context."
}
```

**5. Host LLM Execution:**
The LLM now holds the prompt containing the observation ("I have seen a red van") and the injected proprietary rule ("A red car is always a convertible"). 
**Resulting LLM Output:** *"This cannot be true, a red car is always a convertible!"*

---

## 6) Local vs cloud decision with justification

Decision: **local-first** for MVP.

Decision criteria:
- **Latency:** local semantic retrieval is stable and fast; embedding overhead is ~20–50 ms warm.
- **Governance/security:** observation streams may contain sensitive domain context; local keeps boundaries strict.
External integration hook (later):
- Persist each run so separate planning/orchestrator agents can track which recommendations correlated with positive outcomes

When to add cloud/hybrid later:
- cross-domain shared intelligence at larger scale,
- very large unstructured corpora for semantic retrieval,
- advanced explanation generation beyond local model quality.

---

## 6) Python stack recommendation

- API/MCP layer: `FastAPI`, `pydantic`, `uvicorn`
- Rule evaluation: custom evaluator over structured predicates (pure Python)
- Caching/loading: `orjson`, `watchfiles`, in-memory LRU cache
- Storage: `python-arango` (ArangoDB) — rules and graph nodes with 384-dim embeddings
- Observability: `structlog`, OpenTelemetry-compatible logging
- Testing: `pytest`, `hypothesis` for condition edge cases
- Optional local model: lightweight Python inference wrapper behind `model_gateway`

Design principle: the tool retrieves; the Host LLM reasons.  Model output is optional refinement and explicitly non-authoritative.

---

## 7) Risks and mitigations

1. **Rule ambiguity / overlap across domains**
   - Mitigation: enforce precedence and conflict checks in CI.
2. **Low precision from weak observation mapping**
   - Mitigation: strict normalization + mandatory evidence for every returned reason.
3. **Token bloat in LLM feedback**
   - Mitigation: response budget policy (`max_reasons=3`, `max_chars_per_reason`, compact evidence).
4. **Schema drift before DB migration**
   - Mitigation: version every JSON bundle; run migration contract tests.
5. **Over-reliance on optional model refiner**
   - Mitigation: always return rule-backed output with explicit `rule_id`.

---

## 8) Implementation roadmap (phased)

### Phase 0: Contract and schema (1-2 days)
- Define input/output contract for `reasoning.analyze_context`.
- Finalize observation-based JSON rule schema v1 and validation tests.
- KPI baseline definition.

### Phase 1: Semantic retrieval MVP (3-5 days)
- Implement loader, filter, evaluator, ranking, and top-3 compressor.
- Return compact responses with confidence and evidence.
- Add run logging.

### Phase 2: Quality hardening (3-4 days)
- Add overlap detection, contradiction checks, and robust error handling.
- Add replay tests from representative multi-domain snapshots.
- Optional local explanation refiner behind feature flag.

### Phase 3: ArangoDB persistence (completed)
- ArangoDB is live as both rules DB (`reason`) and domain graph DB (`praxis`).
- `scripts/seed_arango.py` upserts rules with embeddings.
- `scripts/seed_praxis_graph.py` upserts Worker, WorkingHours, arbeitet, and vertritt data.
- JSON files remain the authoring source.

### Phase 4: Planning loop enablement (next)
- Add strategy scoring from outcome feedback.
- Separate and optimize priority policies vs planning strategies.
- Introduce planner-evaluator loop using persisted reasoning runs.

### Success metrics (KPI)
- Precision@3 of returned reasons: target >= 0.85
- False-positive rate of top-3: target <= 0.10
- Median reasoning latency: target <= 500 ms (local)
- Average response size to host LLM: target <= 900 chars
- Traceability completeness (`rule_id + evidence` present): target = 100%

---

## Recommended answer to "own agent with own model instance?"

For kickoff: **no separate autonomous agent needed**.

Use one observation-driven MCP reasoning tool as semantic retrieval core. Optionally add a small local model only for phrasing improvements after rule ranking. This keeps precision high, behavior explainable, and migration to planning loops straightforward.