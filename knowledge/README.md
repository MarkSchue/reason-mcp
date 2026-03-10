This directory holds project-specific domain knowledge (rules and taxonomy).

Physical constants and domain-specific limits ("facts") are expressed directly
as conditions within rules — either as `exact` predicates with literal values or
as `natural_language` text.  There is no separate `facts/` directory.

Structure:
  knowledge/
  └── <project-name>/
      ├── rules/          ← one or more *.json rule pack files
      └── taxonomy/
          └── aliases.json  ← optional: raw_key → canonical_key mapping

Point the server at the correct project folder via:
  REASON_KNOWLEDGE_DIR=./knowledge/<project-name>

The example/ folder ships with the repository as a working reference.
