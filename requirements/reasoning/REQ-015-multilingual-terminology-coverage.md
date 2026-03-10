# REQ-015 Multilingual Terminology Coverage

## User Story
As an international user,
I want context terms in different languages to map to the same underlying concepts,
so that reasoning quality is stable across multilingual inputs.

## Acceptance Criteria
- The system supports language-aware normalization of key terms.
- Equivalent concepts across supported languages can map to shared canonical concepts.
- Semantic matching quality is measured separately per supported language.
- Unsupported language scenarios return explicit, structured limitations.

## Notes
This requirement focuses on terminology and concept mapping, not full translation quality.
