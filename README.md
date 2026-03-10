# reason-mcp

A **general-purpose MCP server** that augments LLM reasoning and planning with
project-specific domain knowledge. The server exposes two tools:

| Tool | Description |
|---|---|
| `reasoning_analyze_context` | Retrieves relevant domain rules and facts for a set of observations, returning a lean knowledge bundle the Host LLM uses to reason. |
| `planning_generate_plan` | Generates a validated execution graph (DAG) for a goal, with a dry-run simulation verifying pre/post-conditions before execution. |

The server is **domain-agnostic** — different projects plug in their own knowledge by
pointing `REASON_KNOWLEDGE_DIR` at a folder of JSON rule packs and fact files.

---

## Quick-start

```bash
# Set up environment
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Use the example knowledge store
cp .env.example .env
# edit .env: REASON_KNOWLEDGE_DIR=./knowledge/example

# Run the server
reason-mcp

# Run tests
pytest
```

## Adding a knowledge domain

```
knowledge/
└── my-project/
    ├── rules/          ← *.json rule pack files (conditions embed facts inline)
    └── taxonomy/
        └── aliases.json  ← raw_sensor_id → OBS_CANONICAL_ID
```

Set `REASON_KNOWLEDGE_DIR=./knowledge/my-project` and restart. No code changes needed.

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
src/reason_mcp/      ← server + tool implementations
knowledge/example/   ← reference knowledge fixtures
tests/               ← unit tests (13 passing)
plans/               ← architecture documentation
requirements/        ← requirement specifications
```
