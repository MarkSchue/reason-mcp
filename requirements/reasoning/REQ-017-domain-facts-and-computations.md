# REQ-017 Unified Conditions Model (Facts As Conditions)

**User Story:**
As a domain expert or knowledge author,
I want to express physical constants, domain-specific limits, and established facts directly as conditions within a rule,
so that there is a single, coherent place to store all rule logic without maintaining a separate facts registry.

**Acceptance Criteria:**
1. **Facts as Conditions:** Physical constants and domain facts (e.g., "standard car weight is 1000 kg", "pressure must stay between 8.0 and 10.0 atm") must be expressible as `exact` predicates or `natural_language` text within the `conditions` block of a rule.  There is no separate `FACT_*` variable system and no separate `facts/` directory.
2. **Exact Conditions with Literal Values:** An `exact` condition list may contain numeric literals directly: `{"left": "OBS_PRESSURE", "op": ">=", "right": 8.0}` — no variable resolution step is required.
3. **Natural Language Facts:** A rule author may embed domain knowledge as free text in the `natural_language` condition field (e.g., `"A standard car weighs 1000 kg."`).
4. **No Resolution Step:** The retrieval pipeline must not perform any `FACT_*` variable look-up or fact-injection step.  When a rule is selected by the compressor, its conditions block — including any embedded facts — is delivered verbatim to the Host LLM.
5. **Host LLM Evaluation:** The Host LLM reads the full conditions block (exact predicates and natural language) and applies the stated facts as part of its reasoning.  The tool exclusively handles retrieval; evaluation is the LLM's responsibility.
