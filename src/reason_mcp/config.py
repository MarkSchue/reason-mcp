"""Configuration loading from environment variables.

ArangoDB credentials are loaded from a ``.env`` file first (via python-dotenv),
and can then be overridden by shell environment variables.  See ``.env.example``
for the full set of supported variables.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env before reading os.environ — shell variables always win.
load_dotenv()


class Config:
    """
    Runtime configuration resolved from environment variables.
    Each project deployment sets its own REASON_* env vars (via .env or shell).
    """

    # ArangoDB connection
    arango_url: str
    arango_user: str
    arango_password: str
    arango_db: str
    arango_rules_coll: str
    arango_edges_coll: str

    # Retrieval defaults
    default_top_k: int
    min_relevance: float
    max_summary_chars: int

    # Observability
    log_level: str
    log_requests: bool
    output_dir: Path

    def __init__(self) -> None:
        # --- ArangoDB ---
        self.arango_url = os.environ.get("REASON_ARANGO_URL", "http://localhost:8529")
        self.arango_user = os.environ.get("REASON_ARANGO_USER", "root")
        self.arango_password = os.environ.get("REASON_ARANGO_PASSWORD", "")
        self.arango_db = os.environ.get("REASON_ARANGO_DB", "reason")
        self.arango_rules_coll = os.environ.get("REASON_ARANGO_RULES_COLL", "rules")
        self.arango_edges_coll = os.environ.get("REASON_ARANGO_EDGES_COLL", "rule_relations")

        # --- Retrieval ---
        self.default_top_k = int(os.environ.get("REASON_DEFAULT_TOP_K", "3"))
        self.min_relevance = float(os.environ.get("REASON_MIN_RELEVANCE", "0.5"))
        self.max_summary_chars = int(os.environ.get("REASON_MAX_SUMMARY_CHARS", "900"))

        # --- Observability ---
        self.log_level = os.environ.get("REASON_LOG_LEVEL", "INFO").upper()
        # When true, each MCP request is written as a Markdown session log to output_dir.
        self.log_requests: bool = os.environ.get("REASON_LOG_REQUESTS", "").lower() in (
            "1", "true", "yes"
        )
        self.output_dir: Path = Path(
            os.environ.get("REASON_OUTPUT_DIR", "./output")
        ).resolve()


# Module-level singleton – import this wherever config is needed.
config = Config()
