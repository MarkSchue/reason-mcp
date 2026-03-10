# REQ-024 Pre- and Post-Conditions for Skills

**User Story:**
As a planning component,
I want strictly defined `pre_conditions` and `post_conditions` (state mutations) for all available skills and capabilities,
so that the system can deterministically simulate world-state changes step-by-step and prevent physically invalid transitions.

**Acceptance Criteria:**
1. **Condition Schemas:** Every skill/capability must explicitly declare what must be true before execution (`pre_conditions`) and how the world state changes afterward (`post_conditions`).
2. **State Simulation:** The planning logic must carry forward mutations step-by-step when evaluating a sequence of actions.
3. **Strict Rejection:** Any drafted step attempting a transition without fulfilled `pre_conditions` must be rejected immediately via deterministic code, bypassing LLM "hallucination".