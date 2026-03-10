# REQ-007 Contract Validation and Errors

## User Story
As an MCP client developer,
I want strict request/response validation and predictable error codes,
so that integrations are robust and easy to troubleshoot.

## Acceptance Criteria
- Request schema rejects unknown top-level fields when in strict mode.
- Validation failures return structured error objects with code and message.
- Error catalog includes validation, unknown observation, knowledge unavailable, timeout, and internal errors.
- Response envelope always includes status and request correlation id.

## Notes
Deterministic error behavior reduces integration ambiguity.
