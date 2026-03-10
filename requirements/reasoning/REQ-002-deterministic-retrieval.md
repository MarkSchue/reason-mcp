# REQ-002 Deterministic Knowledge Retrieval Core

## User Story
As an operations owner,
I want the reasoning tool to assemble and retrieve relevance-matched rules and domain facts deterministically,
so that the context injected into the Host LLM is reproducible, auditable, and suitable for high-trust domains.

## Acceptance Criteria
- Rule and fact retrieval logic is deterministic for identical inputs and rule versions.
- Every knowledge bundle returned includes a `rule_id` or `fact_id` reference.
- The selection of conditions and facts does not require model generation.
- A replay of the same request returns an identical knowledge payload.
- The filter stage supports two complementary retrieval paths:
  - **Structured path**: `observation_id` overlap between the request's observations and `trigger.observations` on a rule.
  - **Semantic keyword path**: `keywords` list on the request matched (case-insensitive intersection) against `trigger.keywords` on a rule.
- A rule is a candidate if it passes the structured path **OR** the keyword path. Rules that define neither criterion are treated as catch-all candidates.

## Notes
The actual logic and rule reasoning is outsourced to the Host LLM. This component solely retrieves the canonical facts deterministically.
