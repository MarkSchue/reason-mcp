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

    def __init__(self) -> None:
        self.knowledge_dir = Path(
            os.environ.get("REASON_KNOWLEDGE_DIR", "./knowledge")
        ).resolve()
        self.default_top_k = int(os.environ.get("REASON_DEFAULT_TOP_K", "3"))
        self.min_relevance = float(os.environ.get("REASON_MIN_RELEVANCE", "0.5"))
        self.max_summary_chars = int(os.environ.get("REASON_MAX_SUMMARY_CHARS", "900"))
        self.log_level = os.environ.get("REASON_LOG_LEVEL", "INFO").upper()
        # When true, the server pre-builds the semantic index at startup instead of
        # waiting for the first semantic_search=true request.
        self.warm_semantic: bool = os.environ.get("REASON_WARM_SEMANTIC", "").lower() in (
            "1", "true", "yes"
        )


# Module-level singleton – import this wherever config is needed.
config = Config()
