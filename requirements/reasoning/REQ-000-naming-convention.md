# Requirement Naming Convention

## Purpose

This folder contains one file per requirement.
Each requirement is documented as a user story with acceptance criteria.

## File naming standard

Use this pattern:

`REQ-<NNN>-<short-kebab-title>.md`

Examples:
- `REQ-001-observation-model.md`
- `REQ-002-deterministic-reasoning.md`

Rules:
- `<NNN>` is a 3-digit sequence starting at `001`.
- `<short-kebab-title>` is lowercase and domain-agnostic.
- One requirement per file.

## Required sections in each requirement file

1. `Title`
2. `User Story` (As a / I want / So that)
3. `Acceptance Criteria`
4. `Notes` (optional, non-normative)
