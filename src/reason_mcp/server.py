"""MCP server entry point.

Registers all tools (reasoning, planning) and starts the server.
This server is general-purpose: domain knowledge is injected at runtime
via the REASON_KNOWLEDGE_DIR environment variable, making it reusable
across different projects and scenarios.
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


def main() -> None:
    """CLI entry point: start the MCP server (defined in pyproject.toml).

    Set REASON_WARM_SEMANTIC=1 to pre-build the ChromaDB vector index and
    download the embedding model before accepting the first request.
    """
    _configure_logging()
    logger.info("starting reason-mcp", knowledge_dir=str(config.knowledge_dir))

    if config.warm_semantic:
        logger.info("REASON_WARM_SEMANTIC=1 — pre-warming semantic index")
        _prewarm_semantic()

    mcp.run()


def index_main() -> None:
    """CLI entry point for the ``reason-mcp-index`` command.

    Loads the knowledge rules, downloads the embedding model if needed, and
    (re)builds the ChromaDB vector index.  Safe to run multiple times; each
    run refreshes the index from the current knowledge files.

    Usage::

        REASON_KNOWLEDGE_DIR=/path/to/knowledge reason-mcp-index
    """
    _configure_logging()
    logger.info("reason-mcp-index: building semantic index", knowledge_dir=str(config.knowledge_dir))
    _prewarm_semantic()
    logger.info("reason-mcp-index: done")


def _prewarm_semantic() -> None:
    """Load rules and call embedder.prewarm() — shared by main() and index_main()."""
    from reason_mcp.knowledge.loader import get_knowledge
    from reason_mcp.tools.reasoning.embedder import prewarm

    rules = get_knowledge(config.knowledge_dir)
    index_dir = config.knowledge_dir / ".semantic_index"
    prewarm(index_dir, rules)


if __name__ == "__main__":
    main()
