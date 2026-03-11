"""Semantic rule retrieval via ArangoDB vector search.

This module implements the semantic (vector) retrieval path of the parallel
dual-path rule retrieval pipeline:

  Path A (filter.py)  – deterministic keyword/observation overlap
  Path B (this file)  – vector-similarity search via ArangoDB APPROX_NEAR_COSINE

Both paths run in parallel for every request and their results are unioned.
This module is always active when the ``[semantic]`` extras are installed; it
degrades gracefully when they are not (the deterministic path still works).

    pip install "reason-mcp[semantic]"

Embedding model
---------------
``paraphrase-multilingual-MiniLM-L12-v2`` — runs on CPU, supports German + English,
~80 MB on first download, ~20-50 ms/query when warm.

Vector backend
--------------
ArangoDB (≥3.12) with a ``vector`` index on the ``embedding`` field of the
``rules`` collection.  Embeddings are stored as rule document properties during
seeding (see ``scripts/seed_arango.py``).  Falls back to Python-side exact
cosine similarity when the native ``APPROX_NEAR_COSINE`` function is unavailable.

Rule text construction for embedding
-------------------------------------
Each rule is encoded as a single concatenated text from four semantic fields:

  1. ``conditions.natural_language``           – the trigger condition
  2. ``reasoning.possible_causes`` (joined)    – why this rule fires
  3. ``recommendation.action``                  – what to do
  4. ``trigger.keywords`` (joined)              – domain vocabulary
"""

from __future__ import annotations

import logging
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Silence noisy third-party loggers early — before any lazy import of
# sentence_transformers / huggingface_hub so that their loggers are already
# capped at ERROR when they first configure themselves.
# ---------------------------------------------------------------------------
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

for _noisy_logger in (
    "sentence_transformers",
    "huggingface_hub",
    "huggingface_hub.repocard",
    "huggingface_hub.utils._http",
    "huggingface_hub.utils._headers",
    "huggingface_hub.file_download",
    "transformers",
    "transformers.modeling_utils",
    "filelock",
    "urllib3.connectionpool",
    "httpx",
    "httpx._client",
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
):
    logging.getLogger(_noisy_logger).setLevel(logging.ERROR)

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Module-level singleton — model is loaded only once per process.
_model: Any = None


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------


def _get_model() -> Any:
    """Lazy-load the SentenceTransformer model."""
    global _model  # noqa: PLW0603
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "semantic search requires 'sentence-transformers'.  "
                "Install it with: pip install 'reason-mcp[semantic]'"
            ) from exc
        # Also mute via the transformers-own verbosity API (belt + suspenders).
        try:
            import transformers as _t  # type: ignore
            _t.utils.logging.set_verbosity_error()
        except Exception:
            pass
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("semantic model loaded", model=_MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Public embedding helpers
# ---------------------------------------------------------------------------


def embed_text(text: str) -> list[float]:
    """Return the embedding vector for a single text string."""
    model = _get_model()
    return model.encode([text], show_progress_bar=False)[0].tolist()


def embed_rule(rule: dict[str, Any]) -> list[float]:
    """Build the canonical embedding text for *rule* and return its vector.

    Concatenates (in order):
      1. conditions.natural_language
      2. reasoning.possible_causes joined with ", "
      3. recommendation.action
      4. trigger.keywords joined with " "
    """
    parts: list[str] = []

    nl = (rule.get("conditions") or {}).get("natural_language", "")
    if nl:
        parts.append(nl)

    causes = (rule.get("reasoning") or {}).get("possible_causes", [])
    if causes:
        parts.append(", ".join(str(c) for c in causes))

    action = (rule.get("recommendation") or {}).get("action", "")
    if action:
        parts.append(action)

    kws = (rule.get("trigger") or {}).get("keywords", [])
    if kws:
        parts.append(" ".join(str(k) for k in kws))

    text = " | ".join(parts) if parts else rule.get("rule_id", "")
    return embed_text(text)


def embed_edge(edge: dict[str, Any]) -> list[float]:
    """Build the canonical embedding text for an *edge* and return its vector.

    Concatenates edge.type and edge.description.
    """
    parts: list[str] = []
    if t := edge.get("type"):
        parts.append(str(t))
    if d := edge.get("description"):
        parts.append(str(d))
    text = " | ".join(parts) if parts else "edge"
    return embed_text(text)


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------


def search_rules(
    query_text: str,
    top_k: int = 5,
    min_score: float = 0.45,
    domain: str | None = None,
) -> list[tuple[str, float]]:
    """Return up to *top_k* ``(rule_id, cosine_score)`` pairs closest to *query_text*.

    Encodes *query_text* with the local SentenceTransformer model, then
    delegates the nearest-neighbour lookup to ArangoDB via
    :func:`reason_mcp.knowledge.arango_client.vector_search`.

    Args:
        query_text:  The natural-language string to embed and search against.
        top_k:       Maximum number of distinct rules to return.
        min_score:   Minimum cosine similarity (0..1) for a hit to be included.
        domain:      When set, only rules whose ``domain`` field matches are considered.

    Returns:
        List of ``(rule_id, score)`` tuples, sorted by descending score.
    """
    query_embedding = embed_text(query_text)

    from reason_mcp.knowledge.arango_client import vector_search as _arango_search

    return _arango_search(
        query_embedding=query_embedding,
        top_k=top_k,
        min_score=min_score,
        domain=domain,
    )
