# REQ-012 Context-to-Knowledge Semantic Matching

## User Story
As an LLM orchestrator,
I want natural language context to be matched semantically to knowledge rules,
so that the tool can retrieve relevant reasons even when explicit structured fields are missing.

## Acceptance Criteria
- The matching stage uses semantic retrieval as the primary rule-selection mechanism.
- The pipeline maps free-text context to candidate rules via embedding-based vector search.
- Candidate ranking combines semantic relevance with rule confidence and severity.
- Matching quality is observable via precision-at-k metrics.

## Notes
This requirement enables broad-domain context interpretation.
