# MCP Contract: Knowledge-Augmented Reasoning (`reasoning_analyze_context`)

## Purpose

Define a concrete, implementation-ready MCP contract for reasoning-first operation.
The contract is domain-agnostic and optimized for precise, compact knowledge injection to an LLM context window.

---

## 1) Tool definition

- **Tool name:** `reasoning_analyze_context` (hosted on `reason-mcp` — the general-purpose MCP server)
- **Goal:** Retrieve domain-specific rules and facts relevant to the given observations, so the calling Host LLM can perform the actual reasoning.
- **Authority model:** The tool retrieves deterministically; the Host LLM reasons.
- **Default response policy:** top-k ranked candidate rules + strictly required domain facts.

---

## 2) Request schema

### JSON Schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "kar.reasoning.analyze_context.request.v1",
  "type": "object",
  "required": ["request_id", "timestamp"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "description": "Caller-generated id for traceability"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "domain": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "description": "Optional domain hint, e.g. production, health, chemistry"
    },
    "subject_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "description": "Optional subject under analysis (system, patient, batch, process, etc.)"
    },
    "context_state": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "description": "Optional high-level state for contextual evaluation"
    },
    "observations": {
      "type": "array",
      "minItems": 0,
      "maxItems": 512,
      "items": {
        "type": "object",
        "required": ["observation_id", "value"],
        "additionalProperties": false,
        "properties": {
          "observation_id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 128
          },
          "value": {
            "type": ["number", "string", "boolean"]
          },
          "unit": {
            "type": "string",
            "maxLength": 16
          },
          "quality": {
            "type": "string",
            "enum": ["good", "uncertain", "bad"]
          },
          "observation_type": {
            "type": "string",
            "maxLength": 64,
            "description": "Optional semantic type for cross-domain normalization"
          },
          "source": {
            "type": "string",
            "maxLength": 64
          }
        }
      }
    },
    "options": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "top_k": {
          "type": "integer",
          "minimum": 1,
          "maximum": 10,
          "default": 3
        },
        "min_confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "default": 0.5
        },
        "max_response_chars": {
          "type": "integer",
          "minimum": 200,
          "maximum": 5000,
          "default": 900
        },
        "include_debug": {
          "type": "boolean",
          "default": false
        },
        "language": {
          "type": "string",
          "enum": ["de", "en"],
          "default": "de"
        },
        "semantic_search": {
          "type": "boolean",
          "default": false,
          "description": "Activate Stage 2 vector-similarity retrieval. Requires the [semantic] extras installed on the server. When true, rule text chunks are embedded with paraphrase-multilingual-MiniLM-L12-v2 and searched in a local ChromaDB index; results are merged with Stage 1 keyword/observation matches."
        },
        "semantic_min_score": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "default": 0.75,
          "description": "Minimum cosine similarity for a Stage 2 hit to be accepted as a candidate. Only relevant when semantic_search is true."
        }
      }
    },
    "context": {
      "type": "object",
      "description": "Optional structured context attributes",
      "additionalProperties": true
    },
    "keywords": {
      "type": "array",
      "description": "Lowercase keywords extracted from a natural-language query (e.g. ['car', 'weight']). Used for semantic keyword matching against rule trigger.keywords when no structured observation IDs are available. May be combined with observations.",
      "maxItems": 50,
      "items": {
        "type": "string",
        "maxLength": 64
      }
    }
  }
}
```

### Request example

```json
{
  "request_id": "req-2026-03-09-0001",
  "timestamp": "2026-03-09T10:15:00Z",
  "domain": "chemistry",
  "subject_id": "SUBJ-17",
  "context_state": "ACTIVE",
  "observations": [
    {"observation_id": "OBS_PRIMARY", "value": 5.8, "unit": "index", "quality": "good", "observation_type": "trend"},
    {"observation_id": "OBS_SECONDARY", "value": 71.2, "unit": "index", "quality": "good", "observation_type": "stability"},
    {"observation_id": "OBS_CONTEXT", "value": "NORMAL", "quality": "good", "observation_type": "state"}
  ],
  "options": {
    "top_k": 3,
    "min_confidence": 0.55,
    "max_response_chars": 900,
    "include_debug": false,
    "language": "de",
    "semantic_search": false,
    "semantic_min_score": 0.75
  },
  "keywords": ["car", "weight", "fleet"]
}
```

---

## 3) Response schema

### JSON Schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "kar.reasoning.analyze_context.response.v1",
  "type": "object",
  "required": ["request_id", "status", "result", "meta"],
  "additionalProperties": false,
  "properties": {
    "request_id": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["ok", "partial", "error"]
    },
    "result": {
      "type": "object",
      "required": ["candidate_knowledge", "summary_for_llm"],
      "additionalProperties": false,
      "properties": {
        "candidate_knowledge": {
          "type": "array",
          "description": "Retrieved rules, conditions, and reasons suitable for the given context",
          "maxItems": 10,
          "items": {
            "type": "object",
            "required": [
              "rank",
              "rule_id",
              "relevance_score",
              "reason_text",
              "conditions"
            ],
            "additionalProperties": false,
            "properties": {
              "rank": {"type": "integer", "minimum": 1},
              "rule_id": {"type": "string"},
              "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
              "severity": {"type": "integer", "minimum": 1, "maximum": 5},
              "reason_text": {"type": "string", "minLength": 1},
              "action_recommendation": {"type": "string", "minLength": 1},
              "conditions": {
                "type": "object",
                "description": "The exact logic and natural language bounds for the LLM to evaluate.  Any domain facts are embedded as literal values in exact predicates or stated in natural_language.",
                "properties": {
                  "exact": { "type": "array" },
                  "natural_language": { "type": "string" }
                }
              },
              "tags": {
                "type": "array",
                "items": {"type": "string"}
              }
            }
          }
        },
        "domain_facts": {
          "type": "object",
          "description": "Deprecated – always empty.  Physical constants and domain facts are now embedded directly in rule conditions.",
          "additionalProperties": true
        },
        "summary_for_llm": {
          "type": "string",
          "description": "Compact context-safe text rendered as '#Rule N: <condition>\n**Reason:** ...\n**Recommendation:** ...' blocks for direct injection into the Host LLM prompt. Empty string when no rules matched."
        },
        "no_match_reason": {
          "type": "string"
        }
      }
    },
    "meta": {
      "type": "object",
      "required": ["knowledge_version", "latency_ms", "applied_policies"],
      "additionalProperties": false,
      "properties": {
        "knowledge_version": {"type": "string"},
        "latency_ms": {"type": "number", "minimum": 0},
        "applied_policies": {
          "type": "array",
          "items": {"type": "string"}
        },
        "candidate_count": {"type": "integer", "minimum": 0},
        "matched_count": {"type": "integer", "minimum": 0},
        "trace_id": {"type": "string"}
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["code", "message"],
        "additionalProperties": false,
        "properties": {
          "code": {"type": "string"},
          "message": {"type": "string"},
          "field": {"type": "string"}
        }
      }
    }
  }
}
```

### Response example (ok)

```json
{
  "request_id": "req-2026-03-09-0001",
  "status": "ok",
  "result": {
    "candidate_knowledge": [
      {
        "rank": 1,
        "rule_id": "R-GEN-ANOMALY-001",
        "relevance_score": 0.89,
        "severity": 3,
        "reason_text": "Observation logically violates expected ranges defined for ACTIVE context.",
        "action_recommendation": "Review recent changes and run targeted diagnostics.",
        "conditions": {
          "exact": [
            {"left": "OBS_PRIMARY", "op": "<", "right": 5.0},
            {"left": "OBS_SECONDARY", "op": "<", "right": 75.0}
          ],
          "natural_language": "Primary stability index must generally remain below 5.0.  Secondary index should stay under 75.0."
        },
        "tags": ["anomaly", "context-aware", "diagnostics"]
      }
    ],
    "summary_for_llm": "#Rule 1: Primary stability index must generally remain below 5.0. Secondary index should stay under 75.0.\n**Reason:** anomaly detected, context-aware trigger\n**Recommendation:** Review recent changes and run targeted diagnostics."
  },
  "meta": {
    "knowledge_version": "ruleset-2026.03.09",
    "latency_ms": 110,
    "applied_policies": ["relevance_policy:v1", "ranking_strategy:v1"],
    "candidate_count": 28,
    "matched_count": 1,
    "trace_id": "trc-c0de-123"
  }
}
```

### Response example (no match / partial)

```json
{
  "request_id": "req-2026-03-09-0002",
  "status": "partial",
  "result": {
    "candidate_knowledge": [],
    "summary_for_llm": "Keine relevanten Regeln gefunden.",
    "no_match_reason": "no_rules_above_threshold"
  },
  "meta": {
    "knowledge_version": "ruleset-2026.03.09",
    "latency_ms": 97,
    "applied_policies": ["relevance_policy:v1", "ranking_strategy:v1"],
    "candidate_count": 19,
    "matched_count": 0,
    "trace_id": "trc-c0de-124"
  }
}
```

---

## 4) Error model

Standard error codes:

- `VALIDATION_ERROR`: request schema violation
- `UNKNOWN_OBSERVATION`: observation id not recognized by taxonomy
- `KNOWLEDGE_UNAVAILABLE`: ruleset not loaded or checksum invalid
- `EVALUATION_ERROR`: deterministic evaluator failed on a rule
- `TIMEOUT`: processing exceeded configured timeout
- `INTERNAL_ERROR`: unclassified failure

Error response shape:

```json
{
  "request_id": "req-2026-03-09-0003",
  "status": "error",
  "result": {
    "reasons": [],
    "summary_for_llm": ""
  },
  "meta": {
    "knowledge_version": "ruleset-2026.03.09",
    "latency_ms": 12,
    "applied_policies": [],
    "trace_id": "trc-c0de-125"
  },
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "observations must contain at least one item",
      "field": "observations"
    }
  ]
}
```

---

## 5) Relevance and token-budget contract

Hard constraints:

- Default `top_k = 3`
- Drop candidates below `min_confidence`
- Remove near-duplicate reasons with same primary cause signature
- `summary_for_llm` must fit `max_response_chars`
- Every returned reason must include at least one explicit evidence item

Ranking guideline (normalized score):

`score = 0.45 * confidence + 0.25 * severity + 0.20 * specificity + 0.10 * actionability`

If no reason passes threshold, return `status = partial` with explicit `no_match_reason`.

---

## 6) Observability and feedback hooks

Per request, log:

- `request_id`, `trace_id`, `knowledge_version`
- `candidate_count`, `matched_count`, top rule ids
- latency breakdown (`load_ms`, `eval_ms`, `rank_ms`, `compose_ms`)
- response size chars
- optional downstream feedback signal (`resolved`, `false_positive`, `ignored`)

These logs become the seed for future planning-loop optimization and strategy scoring.

---

## 7) Versioning and compatibility

- Tool contract version: `v1`
- JSON knowledge schema version: `knowledge_schema_version`
- Backward-compatibility policy:
  - additive fields are allowed,
  - field removals require new major version,
  - unknown request fields rejected in v1 (`additionalProperties=false`).

---

## 8) Suggested implementation file layout (Python)

```text
src/
  mcp_server/
    tools/
      reasoning_analyze_context.py
    schemas/
      reasoning_request_v1.json
      reasoning_response_v1.json
  reasoning/
    loader.py
    filter.py
    evaluator.py
    ranker.py
    compressor.py
    composer.py
  knowledge/
    rules/
    taxonomy/
    catalog.json
  policies/
    relevance_policy.json
    ranking_strategy.json
```

This layout preserves clean boundaries between API contract, deterministic reasoning core, and knowledge/policy artifacts.