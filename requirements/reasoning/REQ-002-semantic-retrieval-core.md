# REQ-002 Semantic Knowledge Retrieval Core

## User Story
As an operations owner,
I want the reasoning tool to assemble and retrieve relevance-matched rules via semantic
vector similarity,
so that the context injected into the Host LLM is reproducible, auditable, and robust
across natural-language, multilingual, and paraphrase input.

## Acceptance Criteria
- Rule retrieval uses a local embedding model (`paraphrase-multilingual-MiniLM-L12-v2`)
  to match a query built from the caller’s `keywords` and observation `observation_id`/`value`
  pairs against the indexed rule corpus.
- Every knowledge bundle returned includes a `rule_id` reference.
- The selection of rules does not require model generation — it is retrieval-only.
- A replay of the same request with the same model and index returns an identical knowledge
  payload.
- Catch-all rules (rules that define no `trigger.observations`, `trigger.keywords`, or
  `trigger.context_states`) are always included regardless of semantic score, so that
  baseline / default guidance is never silently dropped.
- Domain filtering is applied: rules whose `domain` field does not match the request’s
  `domain` are excluded before semantic scoring.

## Notes
The actual logic and rule reasoning is outsourced to the Host LLM. This component solely
retrieves rule-backed candidates and injects them into the LLM context.
