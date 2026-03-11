"""ArangoDB client for rule storage and vector search.

Provides:
  - `get_db()`           — cached database handle
  - `ensure_collections()` — idempotent schema setup (collections + vector index)
  - `get_all_rules(domain)` — return all active rules
  - `upsert_rule(rule)`  — insert or replace a rule document
  - `upsert_edge(edge)`  — insert or replace an edge document
  - `vector_search(...)` — semantic search using APPROX_NEAR_COSINE (3.12+) with
                           Python-side cosine fallback for older deployments

Embedding model: paraphrase-multilingual-MiniLM-L12-v2 → 384-dimensional vectors.
Rules (and edges) must carry an ``embedding`` field for vector search to work.
Run ``scripts/seed_arango.py`` to populate the database from JSON knowledge files.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2
_VECTOR_INDEX_NAME = "reason_vec"


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_db_cached(url: str, user: str, password: str, db_name: str) -> Any:
    """Open or create the target database and return a cached handle."""
    try:
        from arango import ArangoClient  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "python-arango is required.  Install it with: pip install python-arango"
        ) from exc

    client = ArangoClient(hosts=url)
    sys_db = client.db("_system", username=user, password=password, verify=True)
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
        logger.info("created arango database", db=db_name)
    db = client.db(db_name, username=user, password=password, verify=True)
    logger.info("connected to arango", url=url, db=db_name)
    return db


def get_db() -> Any:
    """Return the cached ArangoDB database handle using runtime config."""
    from reason_mcp.config import config

    return _get_db_cached(
        config.arango_url,
        config.arango_user,
        config.arango_password,
        config.arango_db,
    )


def invalidate_connection_cache() -> None:
    """Clear the connection cache (e.g. after credential changes in tests)."""
    _get_db_cached.cache_clear()


# ---------------------------------------------------------------------------
# Schema setup
# ---------------------------------------------------------------------------


def ensure_collections() -> None:
    """Idempotently create collections and the vector index.

    Safe to call on every startup or seed run; does nothing if already present.
    """
    from reason_mcp.config import config

    db = get_db()
    rules_coll = config.arango_rules_coll
    edges_coll = config.arango_edges_coll

    # Document collection for rules
    if not db.has_collection(rules_coll):
        db.create_collection(rules_coll)
        logger.info("created rules collection", name=rules_coll)

    # Edge collection for rule relationships
    if not db.has_collection(edges_coll):
        db.create_collection(edges_coll, edge=True)
        logger.info("created edges collection", name=edges_coll)

    # Persistent index on rule_id for fast lookups
    coll = db.collection(rules_coll)
    existing_names = {idx.get("name") for idx in coll.indexes()}
    if "idx_rule_id" not in existing_names:
        coll.add_persistent_index(fields=["rule_id"], unique=False, sparse=False, name="idx_rule_id")
        logger.info("created rule_id index")

    # NOTE: The vector index is intentionally NOT created here.
    # ArangoDB requires documents with embedding data to exist before training
    # the index (it cannot be created on an empty collection).  Call
    # ``ensure_vector_index(n_docs)`` separately after upserting documents.


def ensure_vector_index(n_docs: int) -> None:
    """Create (or skip if already present) the vector index on the rules collection.

    Must be called **after** documents with ``embedding`` arrays have been
    upserted, because ArangoDB trains the index on existing data.

    Args:
        n_docs: Number of documents in the collection.  Used to compute
            ``nLists`` per the Faiss recommendation of ``15 * sqrt(N)``.
    """
    from reason_mcp.config import config

    db = get_db()
    coll = db.collection(config.arango_rules_coll)
    existing_names = {idx.get("name") for idx in coll.indexes()}
    if _VECTOR_INDEX_NAME in existing_names:
        logger.info("vector index already exists — skipping", index=_VECTOR_INDEX_NAME)
        return

    # nLists: ~15*sqrt(N), clamped to [1, N] so it never exceeds doc count.
    n_lists = max(1, min(n_docs, round(15 * math.sqrt(max(1, n_docs)))))
    try:
        coll.add_index({
            "type": "vector",
            "name": _VECTOR_INDEX_NAME,
            "fields": ["embedding"],
            "params": {
                "dimension": _EMBEDDING_DIM,
                "metric": "cosine",
                "nLists": n_lists,
            },
        })
        logger.info(
            "created vector index",
            index=_VECTOR_INDEX_NAME,
            dim=_EMBEDDING_DIM,
            n_lists=n_lists,
        )
    except Exception as exc:
        logger.warning(
            "vector index creation skipped — falling back to Python-side cosine",
            reason=str(exc),
        )


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


def get_all_rules(domain: str | None = None) -> list[dict[str, Any]]:
    """Return all active rule documents.  Strips the ``embedding`` field."""
    from reason_mcp.config import config

    db = get_db()
    coll = config.arango_rules_coll
    aql = """
        FOR doc IN @@coll
          FILTER doc.active != false
          FILTER @domain == null OR doc.domain == @domain
          RETURN UNSET(doc, "embedding", "_id", "_rev")
    """
    cursor = db.aql.execute(aql, bind_vars={"@coll": coll, "domain": domain})
    return list(cursor)


def upsert_rule(rule: dict[str, Any]) -> None:
    """Insert or replace a rule document.  ``rule["rule_id"]`` is used as ``_key``."""
    from reason_mcp.config import config

    db = get_db()
    coll_name = config.arango_rules_coll
    doc = {**rule, "_key": rule["rule_id"]}
    db.collection(coll_name).insert(doc, overwrite=True, overwrite_mode="replace")


def upsert_edge(edge: dict[str, Any]) -> None:
    """Insert or replace an edge document between two rule nodes.

    The edge dict must have ``from_rule_id`` and ``to_rule_id`` keys.
    ``_key`` is derived as ``<from_rule_id>__<to_rule_id>__<type>``.
    """
    from reason_mcp.config import config

    db = get_db()
    rules_coll = config.arango_rules_coll
    edges_coll = config.arango_edges_coll

    from_key = edge["from_rule_id"]
    to_key = edge["to_rule_id"]
    edge_type = edge.get("type", "related")
    edge_key = f"{from_key}__{to_key}__{edge_type}"

    doc = {
        **{k: v for k, v in edge.items() if k not in ("from_rule_id", "to_rule_id")},
        "_key": edge_key,
        "_from": f"{rules_coll}/{from_key}",
        "_to": f"{rules_coll}/{to_key}",
    }
    db.collection(edges_coll).insert(doc, overwrite=True, overwrite_mode="replace")


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Exact cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def vector_search(
    query_embedding: list[float],
    top_k: int = 5,
    min_score: float = 0.45,
    domain: str | None = None,
) -> list[tuple[str, float]]:
    """Return up to *top_k* ``(rule_id, cosine_score)`` pairs for *query_embedding*.

    Tries ArangoDB native ``APPROX_NEAR_COSINE`` first (requires 3.12+ and the
    vector index).  Falls back to Python-side exact cosine if the AQL function
    is unavailable.

    Returns:
        List of ``(rule_id, score)`` tuples, sorted by descending score.
    """
    from reason_mcp.config import config

    db = get_db()
    coll = config.arango_rules_coll

    # --- Native path ---
    aql_native = """
        FOR doc IN @@coll
          FILTER doc.active != false
          FILTER doc.embedding != null
          FILTER @domain == null OR doc.domain == @domain
          LET score = APPROX_NEAR_COSINE(doc.embedding, @embedding)
          FILTER score >= @min_score
          SORT score DESC
          LIMIT @top_k
          RETURN {rule_id: doc.rule_id, score: score}
    """
    try:
        cursor = db.aql.execute(
            aql_native,
            bind_vars={
                "@coll": coll,
                "domain": domain,
                "embedding": query_embedding,
                "min_score": min_score,
                "top_k": top_k,
            },
        )
        results = [(row["rule_id"], round(float(row["score"]), 4)) for row in cursor]
        logger.info(
            "vector_search (native)",
            hits=len(results),
            min_score=min_score,
            domain=domain,
        )
        return results
    except Exception:
        logger.warning(
            "APPROX_NEAR_COSINE not available — falling back to Python-side cosine",
        )

    # --- Fallback: fetch all, compute cosine in Python ---
    aql_fallback = """
        FOR doc IN @@coll
          FILTER doc.active != false
          FILTER doc.embedding != null
          FILTER @domain == null OR doc.domain == @domain
          RETURN {rule_id: doc.rule_id, embedding: doc.embedding}
    """
    cursor = db.aql.execute(
        aql_fallback,
        bind_vars={"@coll": coll, "domain": domain},
    )
    scored: list[tuple[str, float]] = []
    for row in cursor:
        score = round(_cosine_sim(query_embedding, row["embedding"]), 4)
        if score >= min_score:
            scored.append((row["rule_id"], score))

    results = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]
    logger.info(
        "vector_search (fallback cosine)",
        hits=len(results),
        min_score=min_score,
        domain=domain,
    )
    return results
