# REQ-003 Lean Context Injection & Relevance Compression

## User Story
As a Host LLM orchestrator,
I want the tool to inject the absolute minimum required domain knowledge (rules) into the response,
so that my context window usage stays optimally lean and focused, while still guaranteeing I have every piece of data needed for reasoning.

## Acceptance Criteria
- **Top-K Enforcement:** Output supports a configurable `top_k` with default value `3` to limit the scope of injected rules to the most contextually relevant.
- **Nominal Pruning Check:** The observation payload returned to the LLM must be strictly stripped of irrelevant/nominal observations (Zero-Value Pruning), retaining only the anomalous markers that triggered the rules.
- **Deduplication:** Near-duplicate rules or rules covering identical semantic intent are deduplicated before final output to save tokens.
- **Field Stripping:** Internal metadata within rule JSONs (like `author`, `updated_at`, or internal documentation tags) that are irrelevant for LLM reasoning must be stripped prior to payload delivery.

## Notes
This requirement is the core control for "Lean Context Injection."  Token pressure is minimised by providing exactly what is needed (the bare-metal rule logic including any embedded domain facts or physical constants expressed as conditions) and not a single token more.  Facts are embedded within rule conditions, so selecting the top_k rules is sufficient — no separate fact resolution step is required.
