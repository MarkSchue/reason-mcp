# REQ-026 Component Knowledge Granularity

**User Story:**
As a planning tool,
I want a dedicated storage layer for objective domain and component facts (e.g., "Pump A breaks if run dry for 30s" or "Max tolerance is 10 bar"),
so that technical constraints are cleanly separated from broad overarching business strategies (`planning_policies`) and atomic action definitions (`skills`).

**Acceptance Criteria:**
1. **Dedicated Entity:** A specific `component_knowledge` storage structure captures immutable facts and physical tolerances of the domain.
2. **Contextual Retrieval:** Only component records relevant to the current anomaly or drafted plan are injected into the context window.
3. **Constraint Alignment:** The planner must respect these hardware facts precisely when choosing strategies, overriding base skills if a component's specific limit is stricter.