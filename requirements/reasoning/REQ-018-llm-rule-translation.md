# REQ-018 LLM Rule Translation and Semantic Evaluation

**User Story:**
As a business user or domain expert,
I want to define anomaly detection limits using a mix of exact logic and natural language text,
so that I am not restricted to writing strict mathematical trees when simple human language is sufficient.

**Acceptance Criteria:**
1. **Multi-Modal Rule Schema:** The rule engine schema must support two types of condition inputs simultaneously:
   - `exact`: Strict AST-style predicates with literal values (e.g., `{"left": "OBS_PRESSURE", "op": ">=", "right": 8.0}`).
   - `natural_language`: Plain text instructions (e.g., "always keep pressure between 8 and 10 atm in production").
   Both fields are optional; a rule may use one or both.  Physical constants and domain facts are embedded directly in these fields — no `FACT_*` variable references are used.
2. **Context Bundle Assembly:** The reasoning tool acts as a retrieval engine.  When a rule matches observations, the tool delivers the complete conditions block (including embedded facts as literal values or natural language) to the Host LLM without further transformation.
3. **Execution by Host LLM:** The fully assembled domain context (pruned anomalies, candidate rules with all conditions) is passed back to the Host LLM.  The reasoning, logic execution, and boolean anomaly checks are computed by the LLM externally, not by the tool itself.
4. **Hybrid Rule Delivery:** For mixed rules, the tool packages both the exact predicates and the natural language context symmetrically so the Host LLM can weigh strict boundaries against semantic instructions during its evaluation.
