# REQ-010 Semantic Normalization and Synonyms

## User Story
As a user describing a context in natural language,
I want the tool to normalize semantically equivalent terms,
so that relevant reasons are found even when my wording differs from stored knowledge entries (for example "vehicle" vs "car").

## Acceptance Criteria
- The system supports semantic aliasing between request terms and knowledge terms.
- Equivalent concepts with different surface forms can match the same reasoning rule.
- Matching works when query term and stored term are not exact string matches.
- Semantic normalization can be configured per domain profile.

## Notes
This requirement captures core synonym and concept-equivalence behavior.
