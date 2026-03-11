"""MCP server entry point.

Registers all tools (reasoning, planning) and starts the server.
This server is general-purpose: domain knowledge is stored in ArangoDB and
injected at query time via the knowledge loader.  Connection parameters are
read from environment variables (or a .env file — see .env.example).
"""

from __future__ import annotations

import structlog
from mcp.server.fastmcp import FastMCP

from reason_mcp.config import config
from reason_mcp.tools.planning.tool import register as register_planning
from reason_mcp.tools.reasoning.tool import register as register_reasoning

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="reason-mcp",
    instructions=(
        "Knowledge-augmented reasoning and planning server. "
        "Call `reasoning_analyze_context` to retrieve domain-specific rules and facts "
        "relevant to your observations so you can reason about them. "
        "Call `planning_generate_plan` to produce a validated execution graph for a goal."
    ),
)

# Register tools from each sub-package
register_reasoning(mcp)
register_planning(mcp)


def _configure_logging() -> None:
    """Apply structlog level filter from config."""
    import structlog as _sl

    _sl.configure(
        wrapper_class=_sl.make_filtering_bound_logger(
            __import__("logging").getLevelName(config.log_level)
        ),
    )


def _test_arango_connection() -> None:
    """Verify that ArangoDB is reachable and the database exists.

    Calls :func:`reason_mcp.knowledge.arango_client.ensure_collections` which
    is idempotent — safe to call on every startup.  Logs a warning and
    continues gracefully if the database is unreachable rather than crashing
    the server process.
    """
    try:
        from reason_mcp.knowledge.arango_client import ensure_collections

        ensure_collections()
        logger.info(
            "arango connection verified",
            url=config.arango_url,
            db=config.arango_db,
        )
    except Exception as exc:
        logger.warning(
            "arango connection failed at startup — knowledge queries will fail "
            "until the database is available",
            error=str(exc),
            url=config.arango_url,
            db=config.arango_db,
        )


def main() -> None:
    """CLI entry point: start the MCP server (defined in pyproject.toml)."""
    _configure_logging()
    logger.info(
        "starting reason-mcp",
        arango_url=config.arango_url,
        arango_db=config.arango_db,
    )
    _test_arango_connection()
    mcp.run()


if __name__ == "__main__":
    main()

