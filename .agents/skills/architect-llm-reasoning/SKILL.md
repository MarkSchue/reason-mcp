---
name: architect-llm-reasoning
description: 'Architect Python-first systems that improve LLM/SLM reasoning with external memory, planning, and domain knowledge stores. Use this skill whenever the user asks about reasoning architecture, agent planning loops, retrieval plus reasoning (RAG), capability/prioritization storage, local-vs-cloud model integration, or database design for model decision support. Trigger even if the user does not explicitly ask for "architecture" but describes domain-specific planning, memory, orchestration, or strategy persistence needs.'


---

# Architect LLM/SLM Reasoning Skill

Design Python-only architectures that improve LLM/SLM reasoning by combining:
- model runtime,
- retrieval and memory,
- planning policy,
- and persistent knowledge stores.

Use this skill to produce practical architecture decisions, not generic theory.
If key requirements are missing, ask concise clarifying questions first.

## When to use

- User asks how to architect reasoning/planning for LLMs or SLMs.
- User needs domain knowledge, plans, priorities, or capabilities stored and reused.
- User asks how to choose local vs cloud model deployment.
- User needs a Python stack recommendation for memory + reasoning + orchestration.
- User asks how to persist and evaluate strategy quality over time.

## First-pass requirements capture

Before proposing architecture, capture or infer:
1. Domain (e.g., legal, ops, support, engineering).
2. Latency target (interactive, near-real-time, batch).
3. Data sensitivity/compliance constraints.
4. Model location options (local, cloud, hybrid).
5. Knowledge volatility (static, periodic updates, continuous updates).
6. Explainability/auditability requirement.

If 2 or more are unknown, ask up to 3 focused questions.

## Architecture selection rules

Use this default decision framework:

1. **Choose deployment mode**
   - Prefer **local/hybrid** when strict privacy, offline operation, or low recurring cost matters most.
   - Prefer **cloud/hybrid** when scalability, managed infra, or strong hosted model quality matters most.

2. **Choose storage pattern**
   - Structured business facts and constraints: PostgreSQL/SQLite tables.
   - Semantic recall over long text: vector index (e.g., pgvector, Qdrant, Chroma).
   - Planning policies and priorities: versioned JSON/relational policy tables.
   - Event traces for learning/optimization: append-only event log table.

3. **Choose orchestration shape**
   - Single-step + retrieval: simple request pipeline.
   - Multi-step planning: planner → executor → verifier loop.
   - High reliability needs: add critic/checker stage and retry policies.

4. **Choose retrieval strategy**
   - Start with hybrid retrieval: metadata filter + semantic search.
   - Add reranking when top-k quality is weak.
   - Cache deterministic sub-results.

5. **Choose memory scope**
   - Session memory for short horizon tasks.
   - Durable memory for recurring domain tasks.
   - Strategy memory for plan templates and prioritization heuristics.

## Canonical Python architecture

Prefer this component model unless constraints require otherwise:

- `api/` (FastAPI): receives tasks and returns plans/results.
- `orchestrator/`: controls reasoning workflow and tool calls.
- `planner/`: builds plans from goals, context, and policies.
- `retrieval/`: fetches domain facts and prior plans.
- `memory/`: manages short-term and long-term memory writes/reads.
- `model_gateway/`: local/cloud model abstraction with one Python interface.
- `evaluation/`: tracks success, latency, cost, and plan quality.

## Data model minimum

Recommend at least these entities:

- `knowledge_items(id, domain, content, source, tags, updated_at, confidence)`
- `capabilities(id, name, version, preconditions, limits, owner)`
- `planning_strategies(id, domain, strategy_json, score, created_at, updated_at)`
- `priority_policies(id, policy_json, objective, effective_from, effective_to)`
- `reasoning_runs(id, task, plan_json, outcome, latency_ms, cost, created_at)`
- `feedback_events(id, run_id, signal_type, signal_value, notes, created_at)`

Use schema versioning and migration tooling (e.g., Alembic).

## Local vs cloud integration guidance

When comparing options, always provide:

- Recommended topology,
- latency implications,
- security implications,
- operational complexity,
- and a Python implementation path.

Default recommendation logic:
- If sensitive data + moderate scale: local model + local DB, optional cloud fallback.
- If bursty demand + broad model capability: cloud model + managed DB + async worker queue.
- If mixed constraints: hybrid gateway routing by task class and data sensitivity.

## Planning and prioritization strategy storage

Store strategies as explicit, inspectable artifacts:

- JSON policy objects with version and validity windows.
- Score each strategy by outcome quality over recent runs.
- Keep a fallback default strategy per domain.
- Separate **priority policy** (what matters most) from **planning strategy** (how to solve).

Update loop:
1. Execute plan.
2. Log outcome + telemetry.
3. Re-score strategy.
4. Promote/demote strategy by threshold rules.

## Response contract

When this skill is used, produce output in this exact structure:

1. **Recommended architecture (1-2 paragraphs)**
2. **Component diagram in words**
3. **Storage design (tables/collections + why)**
4. **Reasoning/planning flow (step-by-step)**
5. **Local vs cloud decision with justification**
6. **Python stack recommendation**
7. **Risks and mitigations**
8. **Implementation roadmap (phased)**

Additional quality requirements:
- In section 1, make one explicit primary recommendation (not multiple equal options).
- In section 5, include explicit decision criteria (latency, governance, cost, complexity).
- Clearly separate **priority policy** from **planning strategy** and explain why each is stored separately.
- Include at least one concrete schema or entity example in section 3.
- Include success metrics in section 8 (for example quality, latency, and reliability KPIs).
- In section 3, explicitly include all three storage categories by name: **knowledge**, **planning strategies**, and **capabilities**.

Section 3 required mini-template:
- Knowledge storage: tables/collections and purpose
- Planning strategies storage: tables/collections and purpose
- Capabilities storage: tables/collections and purpose

## Python scope constraint

Only recommend Python tools, frameworks, and code patterns.
Do not provide implementation advice in other languages.

## Reference material

For deeper details, read:
- `references/python-reasoning-architecture.md`

## Quick examples

**Prompt:** "Design a Python architecture for domain-specific planning with a local SLM and strategy memory."

**Expected behavior:** provide component layout, storage schema, reasoning loop, and local-vs-hybrid recommendation.

**Prompt:** "How should I store prioritization rules and capability metadata so a cloud LLM can reason better?"

**Expected behavior:** propose policy/capability schemas, retrieval pattern, governance controls, and rollout plan.