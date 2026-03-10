"""Semantic rule retrieval via local embedding index.

This module implements the semantic (vector) retrieval path of the parallel
dual-path rule retrieval pipeline:

  Path A (filter.py)  – deterministic keyword/observation overlap
  Path B (this file)  – vector-similarity search over rule text chunks

Both paths run in parallel for every request and their results are unioned.
Neither path gates the other.  This module is always active when the
``[semantic]`` extras are installed; it degrades gracefully when they are not
(the deterministic path still returns results).

    pip install "reason-mcp[semantic]"

Embedding model
---------------
``paraphrase-multilingual-MiniLM-L12-v2`` — runs on CPU, supports German + English,
~80 MB on first download, ~20-50 ms/query when warm.

Vector backend
--------------
ChromaDB local-persistent.  Index is stored under
``<REASON_KNOWLEDGE_DIR>/.semantic_index/`` and is rebuilt automatically when the
knowledge cache is invalidated (see :func:`invalidate_semantic_index`).

Chunking strategy
-----------------
Each rule is split into up to four text chunks, each stored as a separate vector
with metadata ``rule_id`` and ``domain``:

- ``conditions``    — natural_language condition text + serialised exact predicates
- ``reasoning``     — possible_causes joined as prose
- ``recommendation``— recommendation action string
- ``keywords``      — trigger.keywords joined as a phrase
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
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
_COLLECTION_NAME = "rule_chunks"

# Module-level singletons so the model and client are loaded only once per process.
_model: Any = None
_chroma_client: Any = None
_collection: Any = None
_current_index_dir: str | None = None


def _get_model() -> Any:
    """Lazy-load the SentenceTransformer model.

    Logger suppression for huggingface_hub, sentence_transformers, etc. lives
    at module level (see top of file) so that it takes effect before these
    packages are first imported, preventing HTTP trace floods.
    """
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


def _get_collection(index_dir: Path) -> Any:
    """Return the persistent Chroma collection, creating it if necessary."""
    global _chroma_client, _collection, _current_index_dir  # noqa: PLW0603
    index_dir_str = str(index_dir)
    if _collection is not None and _current_index_dir == index_dir_str:
        return _collection
    try:
        import chromadb  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "semantic search requires 'chromadb'.  "
            "Install it with: pip install 'reason-mcp[semantic]'"
        ) from exc
    index_dir.mkdir(parents=True, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=index_dir_str)
    _collection = _chroma_client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    _current_index_dir = index_dir_str
    logger.info("chroma collection opened", path=index_dir_str, count=_collection.count())
    return _collection


def _rule_chunks(rule: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return ``(chunk_id, text, chunk_type)`` tuples for a single rule."""
    rule_id: str = rule.get("rule_id", "UNKNOWN")
    domain: str = rule.get("domain", "")
    chunks: list[tuple[str, str, str]] = []

    # Conditions chunk
    cond = rule.get("conditions", {})
    parts: list[str] = []
    if nl := cond.get("natural_language"):
        parts.append(nl)
    for pred in cond.get("exact", []):
        parts.append(f"{pred.get('left')} {pred.get('op')} {pred.get('right')}")
    if parts:
        chunks.append((f"{rule_id}::conditions", " | ".join(parts), "conditions"))

    # Reasoning chunk
    causes = rule.get("reasoning", {}).get("possible_causes", [])
    if causes:
        chunks.append((f"{rule_id}::reasoning", ", ".join(causes), "reasoning"))

    # Recommendation chunk
    action = rule.get("recommendation", {}).get("action", "")
    if action:
        chunks.append((f"{rule_id}::recommendation", action, "recommendation"))

    # Keywords chunk
    kws = rule.get("trigger", {}).get("keywords", [])
    if kws:
        chunks.append((f"{rule_id}::keywords", " ".join(kws), "keywords"))

    return chunks


def build_rule_index(rules: list[dict[str, Any]], index_dir: Path) -> Any:
    """Build (or rebuild) the Chroma collection from *rules*.

    Existing documents are replaced if the collection already exists.
    Returns the Chroma collection.
    """
    collection = _get_collection(index_dir)
    model = _get_model()

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, str]] = []

    for rule in rules:
        rule_id = rule.get("rule_id", "UNKNOWN")
        domain = rule.get("domain", "")
        for chunk_id, text, chunk_type in _rule_chunks(rule):
            ids.append(chunk_id)
            texts.append(text)
            metadatas.append({"rule_id": rule_id, "domain": domain, "chunk_type": chunk_type})

    if not ids:
        logger.warning("no chunks to index", total_rules=len(rules))
        return collection

    embeddings: list[list[float]] = model.encode(texts, show_progress_bar=False).tolist()

    # Upsert in batches of 500 to stay within Chroma limits
    batch = 500
    for start in range(0, len(ids), batch):
        collection.upsert(
            ids=ids[start : start + batch],
            embeddings=embeddings[start : start + batch],
            documents=texts[start : start + batch],
            metadatas=metadatas[start : start + batch],
        )

    logger.info("semantic index built", chunks=len(ids), rules=len(rules))
    return collection


def search_rules(
    query_text: str,
    index_dir: Path,
    rules: list[dict[str, Any]],
    top_k: int = 5,
    min_score: float = 0.75,
    domain: str | None = None,
) -> list[tuple[str, float]]:
    """Return up to *top_k* ``(rule_id, cosine_score)`` pairs closest to *query_text*.

    Each rule may have multiple indexed chunks (conditions, reasoning, recommendation,
    keywords).  The *best* cosine score across all chunks for a given rule is returned.

    Args:
        query_text:  The natural-language string to embed and search against.
        index_dir:   Path to the persistent Chroma index directory.
        rules:       Full active rule list — used to (re)build the index on first call.
        top_k:       Maximum number of distinct rules to return.
        min_score:   Minimum cosine similarity (0..1) for a chunk to be included.
        domain:      When set, only chunks whose metadata ``domain`` matches are considered.

    Returns:
        List of ``(rule_id, score)`` tuples, sorted by descending score.
    """
    collection = _get_collection(index_dir)

    # Rebuild index if empty (first run, or after invalidation)
    if collection.count() == 0:
        build_rule_index(rules, index_dir)

    # Guard: nothing to query — return empty rather than crashing Chroma
    if collection.count() == 0:
        logger.warning("semantic index is empty after build attempt — no rules to search")
        return []

    model = _get_model()
    query_embedding: list[float] = model.encode([query_text], show_progress_bar=False)[0].tolist()

    where: dict[str, Any] | None = {"domain": domain} if domain else None

    # Retrieve more candidates than top_k to account for deduplication across chunks.
    # Ensure top_k >= 1 so the multiplier never produces 0.
    safe_top_k = max(top_k, 1)
    n_results = min(safe_top_k * 4, collection.count())
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["distances", "metadatas"],
    )

    distances: list[float] = results["distances"][0]
    metas: list[dict[str, str]] = results["metadatas"][0]

    # Per-rule: keep the best (highest) cosine score across all chunks
    best_scores: dict[str, float] = {}
    for dist, meta in zip(distances, metas):
        similarity = round(1.0 - dist, 4)
        if similarity < min_score:
            continue
        rule_id = meta["rule_id"]
        if rule_id not in best_scores or similarity > best_scores[rule_id]:
            best_scores[rule_id] = similarity

    # Sort by descending score, cap at top_k
    matched: list[tuple[str, float]] = sorted(
        best_scores.items(), key=lambda x: x[1], reverse=True
    )[:top_k]

    logger.info(
        "semantic search",
        query_len=len(query_text),
        hits=len(matched),
        min_score=min_score,
        domain=domain,
    )
    return matched


def prewarm(index_dir: Path, rules: list[dict[str, Any]]) -> None:
    """Unconditionally (re)build the Chroma index and ensure the model is loaded.

    Intended for server-startup warm-up or the ``reason-mcp-index`` CLI command.
    Unlike the lazy path in :func:`search_rules`, this always calls
    :func:`build_rule_index` regardless of whether the collection is already
    populated, so it also refreshes a stale index.
    """
    logger.info("prewarming semantic index", index_dir=str(index_dir), rules=len(rules))
    build_rule_index(rules, index_dir)
    logger.info("semantic index ready", chunks=_get_collection(index_dir).count())


def invalidate_semantic_index(index_dir: Path) -> None:
    """Delete all vectors from the collection so it will be rebuilt on next search.

    Called automatically by :func:`reason_mcp.knowledge.loader.invalidate_cache`.
    """
    global _collection  # noqa: PLW0603
    try:
        collection = _get_collection(index_dir)
        ids = collection.get(include=[])["ids"]
        if ids:
            collection.delete(ids=ids)
            logger.info("semantic index cleared", removed=len(ids))
        _collection = None
    except Exception:
        logger.warning("semantic index invalidation skipped (not built yet)")
