# Knowledge-Augmented Reasoning Semantic Matching Approach Plan (Domain-Agnostic MVP)

## Scope and alignment

This document extends and aligns with:
- `plans/knowledge-augmented-reasoning-architecture.md`
- `plans/knowledge-augmented-reasoning-mcp-contract.md`
- `requirements/REQ-010-semantic-normalization-and-synonyms.md` to `requirements/REQ-015-multilingual-terminology-coverage.md`

Goal: make natural-language context robustly match stored reasoning knowledge even when wording differs (e.g., "vehicle" vs "car") while preserving deterministic, auditable final reasoning.

---

## 1) Recommended architecture (1-2 paragraphs)

Primary recommendation: add a **Semantic Interpretation Layer** before deterministic rule scoring. This layer maps free-text context and observation labels to canonical concepts (synonyms, paraphrases, multilingual terms), produces explainable semantic candidates, and passes only high-quality candidates into the deterministic reasoner.

The final reason output remains deterministic and evidence-based; language-model capabilities are used to improve semantic recall, not to override rule truth. This preserves trust and auditability while unlocking broad cross-domain applicability.

---

## 2) Component diagram in words

Semantic-aware reasoning path:

1. **Context Intake** receives natural-language context and optional structured observations.
2. **Normalizer** standardizes casing, token forms, units, and domain aliases.
3. **Concept Mapper** maps terms to canonical concepts (synonym graph + embedding retrieval).
4. **Paraphrase Matcher** computes semantic similarity between context snippets and rule descriptions/templates.
5. **Ambiguity Resolver** detects multi-meaning matches and applies policy (clarify, constrain, or continue).
6. **Candidate Builder** emits candidate rule ids with semantic evidence and confidence.
7. **Deterministic Evaluator** applies rule conditions on normalized observations/context.
8. **Rank Fusion** combines semantic relevance and deterministic confidence into final ranking.
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

**Later (SQLite):**
- `knowledge_items(id, rule_id, domain, description, conditions_json, reasoning_template, tags_json, version, updated_at)`
- `concepts(id, canonical_term, domain, metadata_json, updated_at)`
- `concept_aliases(id, concept_id, alias, language, weight, source, updated_at)`

Purpose: support robust context-to-knowledge matching across variants and languages.

### Capabilities storage: tables/collections and purpose

**Now (JSON file):**
- `capabilities/capabilities.json` with supported languages, semantic methods, and ambiguity behaviors

**Later (SQLite):**
- `capabilities(id, name, version, preconditions_json, limits_json, owner, status, updated_at)`

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

Semantic matching + deterministic reasoning flow:

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
6. Evaluate deterministic rule conditions for candidate set.
7. Fuse scores:
   - semantic relevance,
   - deterministic confidence,
   - severity/actionability.
8. Build response:
   - top-k reasons,
   - deterministic evidence,
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
- Embeddings/retrieval: `sentence-transformers`, `numpy`, `faiss-cpu` or `pgvector`
- Rule reasoning: custom deterministic evaluator (pure Python)
- Persistence/migration: `sqlite3` -> `SQLAlchemy` + `Alembic`
- Observability: `structlog`, OpenTelemetry-compatible traces
- Evaluation harness: `pytest`, `pandas`, `scikit-learn` metrics for semantic quality

Principle: language models support semantic matching and disambiguation, while final reason selection remains deterministic.

---

## 7) Risks and mitigations

1. **False semantic matches (high recall, low precision)**
   - Mitigation: confidence thresholds + deterministic gate before final output.
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
- Implement concept/alias store and deterministic normalization pipeline.
- Add synonym mapping and explainable term trace output.

### Phase 2: Paraphrase + semantic retrieval (4-6 days)
- Add embedding retrieval for free-text context to rule candidates.
- Implement ranking fusion with deterministic scores.

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
