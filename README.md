# reason-mcp

A **general-purpose MCP server** that augments LLM reasoning and planning with
project-specific domain knowledge. The server exposes two tools:

| Tool | Description |
|---|---|
| `reasoning_analyze_context` | Retrieves relevant domain rules and facts for a set of observations, returning a lean knowledge bundle the Host LLM uses to reason. |
| `planning_generate_plan` | Generates a validated execution graph (DAG) for a goal, with a dry-run simulation verifying pre/post-conditions before execution. |

The server is **domain-agnostic** — domain knowledge is stored in ArangoDB and
injected at query time.  Rules are seeded from JSON files via `scripts/seed_arango.py`.

---

## Quick-start

```bash
# Set up environment
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,semantic]"

# Configure ArangoDB credentials
cp .env.example .env
# Edit .env: set REASON_ARANGO_URL, REASON_ARANGO_USER, REASON_ARANGO_PASSWORD

# Seed the built-in example rules into ArangoDB
python scripts/seed_arango.py

# Run the server
reason-mcp

# Run tests
pytest
```

## Adding a knowledge domain

1. Add a new module to the `seeds/` package, e.g. `seeds/my_domain.py`:

```python
RULES: list[dict] = [
    {
        "rule_id": "MY-001",
        "domain": "my_domain",
        "active": True,
        "trigger": {"keywords": ["example"]},
        "conditions": {"natural_language": "Example condition."},
        "reasoning": {"possible_causes": ["example cause"]},
        "recommendation": {"action": "Do something.", "urgency": "low"},
        "scoring": {"severity": 1, "specificity": 0.8},
    },
]
EDGES: list[dict] = []
```

2. Register it in `seeds/__init__.py` by importing and extending `RULES`/`EDGES`.

3. Seed into ArangoDB:

```bash
python scripts/seed_arango.py
```

No code changes to the server are needed.

## Documentation

| Document | Description |
|---|---|
| [plans/architecture/mcp-server-architecture.md](plans/architecture/mcp-server-architecture.md) | General-purpose server — layout, deployment, design principles |
| [plans/architecture/reasoning-tool-architecture.md](plans/architecture/reasoning-tool-architecture.md) | Reasoning tool component deep-dive |
| [plans/architecture/planning-tool-architecture.md](plans/architecture/planning-tool-architecture.md) | Planning tool component deep-dive |
| [plans/reasoning/](plans/reasoning/) | Reasoning MCP contract and architecture plan |
| [plans/planning/](plans/planning/) | Planning MCP contract and architecture plan |
| [requirements/reasoning/](requirements/reasoning/) | Reasoning requirements (REQ-001 … REQ-018) |
| [requirements/planning/](requirements/planning/) | Planning requirements (REQ-016 … REQ-027) |

## Project layout

```
src/reason_mcp/          ← server + tool implementations
  knowledge/
    arango_client.py     ← ArangoDB connection, CRUD, vector search
    loader.py            ← in-process LRU cache over ArangoDB
  tools/reasoning/
    embedder.py          ← SentenceTransformer embeddings + search_rules()
    filter.py            ← dual-path retrieval (deterministic + semantic)
seeds/                   ← initial domain knowledge as Python data
  __init__.py            ← aggregates RULES + EDGES from all domain modules
  car_facts.py           ← CarFacts domain (CAR-1, CAR-2, CAR-3)
  praxis.py              ← Praxisbesetzung domain (PRAX-1, PRAX-2 + fallback edges)
  fleet_and_industrial.py ← fleet_tracking + industrial (6 rules)
scripts/seed_arango.py   ← idempotent seed script (seeds package → ArangoDB)
tests/                   ← unit tests (28 passing)
plans/                   ← architecture documentation
requirements/            ← requirement specifications
```

