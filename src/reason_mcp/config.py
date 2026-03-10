"""Configuration loading from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


class Config:
    """
    Runtime configuration resolved from environment variables.
    Each project deployment sets its own REASON_* env vars (via .env or shell).
    """

    knowledge_dir: Path
    default_top_k: int
    min_relevance: float
    max_summary_chars: int
    log_level: str
    warm_semantic: bool
    log_requests: bool
    output_dir: Path

    def __init__(self) -> None:
        self.knowledge_dir = Path(
            os.environ.get("REASON_KNOWLEDGE_DIR", "./knowledge")
        ).resolve()
        self.default_top_k = int(os.environ.get("REASON_DEFAULT_TOP_K", "3"))
        self.min_relevance = float(os.environ.get("REASON_MIN_RELEVANCE", "0.5"))
        self.max_summary_chars = int(os.environ.get("REASON_MAX_SUMMARY_CHARS", "900"))
        self.log_level = os.environ.get("REASON_LOG_LEVEL", "INFO").upper()
        # When true, the server pre-builds the semantic index at startup instead of
        # waiting for the first request to trigger lazy index construction.
        self.warm_semantic: bool = os.environ.get("REASON_WARM_SEMANTIC", "").lower() in (
            "1", "true", "yes"
        )
        # When true, each MCP request is written as a Markdown session log to output_dir.
        self.log_requests: bool = os.environ.get("REASON_LOG_REQUESTS", "").lower() in (
            "1", "true", "yes"
        )
        self.output_dir: Path = Path(
            os.environ.get("REASON_OUTPUT_DIR", "./output")
        ).resolve()


# Module-level singleton – import this wherever config is needed.
config = Config()
