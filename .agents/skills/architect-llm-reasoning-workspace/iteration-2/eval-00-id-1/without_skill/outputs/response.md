Use a local-first Python architecture with FastAPI, SQLAlchemy, and PostgreSQL/pgvector.
Keep knowledge, planning strategies, and capabilities in separate tables and run a planner-executor-verifier loop.

Suggested data: knowledge_items, planning_strategies, capabilities, reasoning_runs, feedback_events.

Flow: classify task, retrieve context, plan, execute, verify, log results.

Local is generally best for governance and latency; cloud can help for complex or bursty tasks.
