# Knowledge-Augmented Reasoning Semantic Matching Approach Plan (Domain-Agnostic MVP)

## Scope and alignment

This document extends and aligns with:
- `plans/knowledge-augmented-reasoning-architecture.md`
- `plans/knowledge-augmented-reasoning-mcp-contract.md`
- `requirements/REQ-010-semantic-normalization-and-synonyms.md` to `requirements/REQ-015-multilingual-terminology-coverage.md`

Goal: make natural-language context robustly match stored reasoning knowledge even when wording differs (e.g., "vehicle" vs "car") while preserving auditable, evidence-based final reasoning.

---

## 1) Recommended architecture (1-2 paragraphs)

Primary recommendation: the **Semantic Interpretation Layer** is the sole retrieval mechanism. It maps free-text context and observation labels to canonical concepts (synonyms, paraphrases, multilingual terms) via embedding-based search, producing explainable semantic candidates that are ranked and compressed by the compressor.

The final rule output is evidence-based: every returned rule carries an explicit `rule_id` and relevance score. Language-model capabilities improve semantic recall; they do not override rule content. This preserves trust and auditability while unlocking broad cross-domain applicability.

---

## 2) Component diagram in words

Semantic-aware reasoning path:

1. **Context Intake** receives natural-language context and optional structured observations.
2. **Normalizer** standardizes casing, token forms, units, and domain aliases.
3. **Concept Mapper** maps terms to canonical concepts (synonym graph + embedding retrieval).
4. **Paraphrase Matcher** computes semantic similarity between context snippets and rule descriptions/templates.
5. **Ambiguity Resolver** detects multi-meaning matches and applies policy (clarify, constrain, or continue).
6. **Candidate Builder** emits candidate rule ids with semantic evidence and confidence.
7. **Relevance Ranker** scores candidates by semantic similarity, severity, and confidence.
8. **Rank Fusion** combines semantic relevance and rule confidence into final ranking.
9. **Explainability Composer** returns reasons, evidence, and semantic match trace.
10. **Feedback Logger** stores mappings, outcomes, and ambiguity events for continuous tuning.

---

## 3) Storage design (tables/collections + why)

### Knowledge storage: tables/collections and purpose

**Now (JSON files):**
- `knowledge/rules/*.json`: canonical reasoning rules
- `knowledge/semantic/concepts.json`: canonical concepts and aliases
- `knowledge/semantic/synonym_edges.json`: concept-equivalence graph
- `knowledge/semantic/paraphrase_examples.json`: paraphrase pairs for evaluation

**Runtime store (ArangoDB):**
- `rules` collection in the `reason` database stores rule documents with 384-dim embeddings.
- A separate synonym/concept JSON file (`knowledge/taxonomy/context_terms.json`) provides alias
  lookup; this may be migrated to ArangoDB as a `concepts` vertex collection if needed at scale.

Purpose: support robust context-to-knowledge matching across variants and languages.

### Capabilities storage: tables/collections and purpose

**Now (JSON file):**
- `capabilities/capabilities.json` with supported languages, semantic methods, and ambiguity behaviors

**Runtime (JSON + ArangoDB):**
- `capabilities.json` defines supported languages, semantic methods, and ambiguity behaviors.
- If capability metadata grows, it can be migrated to an ArangoDB `capabilities` collection.

Purpose: make semantic feature availability explicit and testable.

### Concrete schema example (semantic concept entry)

```json
{
  "concept_id": "C-VEHICLE-001",
  "canonical_term": "car",
  "domain": "generic",
  "aliases": [
    {"term": "vehicle", "language": "en", "weight": 0.92},
    {"term": "automobile", "language": "en", "weight": 0.88},
    {"term": "Auto", "language": "de", "weight": 0.95}
  ],
  "related_terms": ["transport", "fleet"],
  "notes": "Maps broad transport references to canonical car concept in baseline profile",
  "version": "1.0.0",
  "active": true
}
```

---

## 4) Reasoning flow (step-by-step)

Semantic matching + rule-backed reasoning flow:

1. Validate request payload and normalize text/observation forms.
2. Extract key entities/terms from context using rule-safe parser + optional LM parser.
3. Map extracted terms to canonical concepts via:
   - alias dictionary,
   - embedding nearest-neighbor retrieval,
   - optional model disambiguation prompt.
4. Compute semantic candidate set for rules (description, tags, templates, concept links).
5. Detect ambiguity:
   - if semantic confidence < threshold or multiple concepts overlap,
   - apply policy: request clarification, constrain output, or continue with warnings.
6. Retrieve candidate rules via the semantic vector index and catch-all fallback.
7. Fuse scores:
   - semantic relevance,
   - rule confidence (confidence_prior),
   - severity/actionability.
8. Build response:
   - top-k rules,
   - rule-backed evidence,
   - semantic mapping trace (`input_term -> canonical_term`).
9. Log telemetry and feedback for strategy tuning.

External integration hook (later):
- Export domain-specific matching policies and outcomes so a separate planning/orchestrating bot can learn to improve synonym weighting and ambiguity thresholds.

---

## 5) Local vs cloud decision with justification

Decision: **local-first hybrid-ready**.

Decision criteria:
- **Latency:** local embedding + dictionary mapping is predictable for interactive use.
- **Governance/security:** sensitive context stays local by default.
- **Cost:** local semantic stack reduces token spend for high-frequency requests.
- **Complexity:** optional cloud fallback only for hard ambiguity cases keeps architecture manageable.

Recommended policy:
- Use local models/components for default semantic mapping.
- Escalate to cloud only when ambiguity remains unresolved and policy allows it.

---

## 6) Python stack recommendation

- API/orchestration: `FastAPI`, `pydantic`, `uvicorn`
- Text normalization: `regex`, `rapidfuzz`, `unicodedata`
- Embeddings/retrieval: `sentence-transformers`, `numpy`
- Vector + graph store: `python-arango` (ArangoDB); `APPROX_NEAR_COSINE` for vector search,
  AQL FOR/PRUNE for graph traversal; Python-side cosine fallback for older clusters
- Rule reasoning / ranking: custom relevance ranker (pure Python)
- Observability: `structlog`, OpenTelemetry-compatible traces
- Evaluation harness: `pytest`, `pandas`, `scikit-learn` metrics for semantic quality

Principle: language models support semantic matching and disambiguation; final rule selection is always rule-backed and evidence-traceable.

---

## 7) Risks and mitigations

1. **False semantic matches (high recall, low precision)**
   - Mitigation: confidence thresholds before final output selection.
2. **Domain drift in synonym sets**
   - Mitigation: versioned concept store + periodic review + feedback-driven updates.
3. **Opaque semantic behavior**
   - Mitigation: expose mapping traces and semantic confidence in debug/audit mode.
4. **Ambiguity not handled safely**
   - Mitigation: explicit ambiguity policy with constrained outputs and optional clarifying question.
5. **Multilingual inconsistency**
   - Mitigation: language-specific normalization profiles and per-language quality KPIs.

---

## 8) Implementation roadmap (phased)

### Phase 0: Requirement-to-capability mapping (1-2 days)
- Map REQ-010..REQ-015 to measurable capabilities and policies.
- Define semantic quality metrics and baseline test set.

### Phase 1: Semantic normalization MVP (3-5 days)
- Implement concept/alias store and semantic normalization pipeline.
- Add synonym mapping and explainable term trace output.

### Phase 2: Paraphrase + semantic retrieval (4-6 days)
- Add embedding retrieval for free-text context to rule candidates.
- Implement ranking fusion with semantic relevance scores.

### Phase 3: Ambiguity and multilingual hardening (4-6 days)
- Add ambiguity detection/resolution policies.
- Add multilingual terminology mapping for supported languages.

### Phase 4: Continuous quality loop (next)
- Add regression suite for paraphrases and multilingual variants.
- Tune concept weights and policies from feedback events.

### Success metrics (KPI)
- Synonym mapping accuracy on gold set: target >= 0.90
- Paraphrase retrieval Precision@3: target >= 0.85
- Ambiguity false-resolution rate: target <= 0.08
- Semantic trace coverage in responses: target = 100% (debug mode)
- End-to-end median latency increase vs baseline: target <= +120 ms

---

## Requirement coverage map

- **REQ-010**: concept/alias normalization + synonym graph
- **REQ-011**: paraphrase robustness benchmarks + regression tests
- **REQ-012**: semantic candidate generation from free-text context
- **REQ-013**: semantic trace (`input_term -> canonical_term`) in output/logs
- **REQ-014**: ambiguity detection and policy-driven resolution
- **REQ-015**: multilingual concept mapping and language-specific evaluation
