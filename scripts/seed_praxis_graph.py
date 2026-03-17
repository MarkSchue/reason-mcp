#!/usr/bin/env python
"""Seed the praxis graph database with nodes and edges from JSON files.

Reads all ``*.json`` files under ``seeds/nodes/`` and ``seeds/edges/``,
generates embeddings for each node description, and upserts everything into
the ArangoDB *praxis* database.  Idempotent — safe to run repeatedly.

Usage::

    python scripts/seed_praxis_graph.py
    python scripts/seed_praxis_graph.py --dry-run
    python scripts/seed_praxis_graph.py --seeds-dir /path/to/seeds

Prerequisites:
  - ArangoDB running (configure via .env or REASON_ARANGO_* env vars)
  - pip install "reason-mcp[semantic]"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------


def _load_json_files(directory: Path) -> list[dict[str, Any]]:
    """Load and merge all ``*.json`` files in *directory*.

    Each file may contain a JSON array or a single object.  Returns a flat
    list of all items found.
    """
    if not directory.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            items.extend(raw)
        elif isinstance(raw, dict):
            items.append(raw)
        print(f"  Loaded {len(raw) if isinstance(raw, list) else 1} item(s) from {path.name}")
    return items


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


def _embed(text: str) -> list[float]:
    """Return the 384-dim embedding vector for *text*."""
    from reason_mcp.tools.reasoning.embedder import embed_text
    return embed_text(text)


def _extract_keywords(node: dict[str, Any]) -> list[str]:
    """Auto-derive a searchable keyword list from well-known node fields.

    Explicit ``keywords`` in the node document always take precedence and are
    returned unchanged.  This fallback fires only when ``keywords`` is absent,
    ensuring backwards compatibility without silently overwriting hand-crafted
    keyword sets.

    The extraction is **domain-agnostic**: every user-defined field is scanned
    automatically.  The ``name`` field (if present) receives special treatment
    (full value + individual tokens) because it is the most common human
    identifier.  All other string and list-of-string fields are included
    generically.

    Skipped keys (internal / computed):
    ``_key``, ``_id``, ``_rev``, ``_from``, ``_to``,
    ``embedding``, ``keywords_embedding``, ``keywords``, ``description``.
    """
    if node.get("keywords"):
        return node["keywords"]

    _SKIP_FIELDS: set[str] = {
        "_key", "_id", "_rev", "_from", "_to",
        "embedding", "keywords_embedding", "keywords", "description",
    }

    kws: list[str] = []

    # Special-case ``name`` — full value + individual tokens
    name = node.get("name", "")
    if name:
        kws.append(name.lower())
        kws.extend(t.lower() for t in name.split() if t)

    for field, value in node.items():
        if field in _SKIP_FIELDS or field == "name":
            continue
        if isinstance(value, str) and value:
            kws.append(value.lower())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    kws.append(item.lower())

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for kw in kws:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def _extract_edge_keywords(edge: dict[str, Any], from_doc: dict[str, Any] | None, to_doc: dict[str, Any] | None) -> list[str]:
    """Auto-derive a keyword list for an edge from its label, type, and endpoint names.

    Returns explicit ``keywords`` unchanged when present.
    """
    if edge.get("keywords"):
        return edge["keywords"]

    kws: list[str] = []

    # Label tokens (keep only tokens with >2 chars)
    label = edge.get("label", "")
    if label:
        kws.extend(t.lower() for t in label.split() if len(t) > 2)

    # Edge type
    etype = edge.get("type", "")
    if etype:
        kws.append(etype.lower())

    # Endpoint names
    for doc in (from_doc, to_doc):
        if doc:
            name = doc.get("name", "")
            if name:
                kws.append(name.lower())
                kws.extend(t.lower() for t in name.split() if t)

    seen: set[str] = set()
    result: list[str] = []
    for kw in kws:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def _compose_edge_description(edge: dict[str, Any], from_doc: dict[str, Any] | None, to_doc: dict[str, Any] | None) -> str:
    """Create a natural-language description for an edge.

    Uses the ``label`` field when available; otherwise composes from
    the edge type and endpoint names/descriptions.
    """
    label = edge.get("label", "")
    if label:
        return label
    etype = edge.get("type", "")
    from_name = (from_doc.get("name") if from_doc else None) or edge.get("from_node_id", "?")
    to_name = (to_doc.get("name") if to_doc else None) or edge.get("to_node_id", "?")
    to_desc = to_doc.get("description", "") if to_doc else ""
    desc = f"{from_name} {etype} {to_name}"
    if to_desc:
        desc += f" ({to_desc})"
    return desc


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------


def seed(seeds_dir: Path, dry_run: bool = False) -> None:
    nodes_dir = seeds_dir / "nodes"
    edges_dir = seeds_dir / "edges"

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Loading seed data from {seeds_dir}")

    # --- Load raw data ---
    print("\n── Nodes ──")
    nodes = _load_json_files(nodes_dir)
    print(f"  Total nodes: {len(nodes)}")

    print("\n── Edges ──")
    edges = _load_json_files(edges_dir)
    print(f"  Total edges: {len(edges)}")

    if not nodes and not edges:
        print("\n[WARNING] No data found — nothing to seed.")
        return

    if dry_run:
        print("\n── Dry-run preview ──")
        for node in nodes:
            text = node.get("description", node.get("name", node.get("node_id", "")))
            keywords = _extract_keywords(node)
            print(f"  NODE  {node['node_id']!r:45s}  type={node.get('type', '?')}")
            print(f"        embed({text[:60]!r}...)")
            print(f"        keywords={keywords}")
        for edge in edges:
            desc = edge.get("label", edge.get("description", ""))
            keywords = _extract_edge_keywords(edge, None, None)
            print(
                f"  EDGE  {edge.get('edge_id', '?')!r:45s}  "
                f"{edge['from_node_id']} --[{edge['type']}]--> {edge['to_node_id']}"
            )
            print(f"        desc={desc[:60]!r}")
            print(f"        keywords={keywords}")
        print("\n[DRY RUN] No changes written to ArangoDB.")
        return

    # --- Set up DB schema ---
    print("\n── Setting up ArangoDB schema (praxis) ──")
    from reason_mcp.knowledge.arango_client import ensure_graph_schema

    ensure_graph_schema()

    from reason_mcp.knowledge.arango_client import (
        ensure_graph_vector_indexes,
        upsert_node,
        upsert_graph_edge,
    )

    # --- Upsert nodes (with embeddings and keywords) ---
    print(f"\n\u2500\u2500 Upserting {len(nodes)} node(s) \u2500\u2500")
    for node in nodes:
        node_id = node["node_id"]
        text = node.get("description", node.get("name", node_id))
        keywords = _extract_keywords(node)
        kw_text = " ".join(keywords)
        print(f"  Embedding node {node_id!r} ...", end=" ", flush=True)
        embedding = _embed(text)
        keywords_embedding = _embed(kw_text)
        upsert_node({**node, "keywords": keywords, "embedding": embedding, "keywords_embedding": keywords_embedding})
        print("done")

    # --- Create / refresh vector indexes (after documents exist) ---
    print(f"\n\u2500\u2500 Ensuring graph vector indexes \u2500\u2500")
    ensure_graph_vector_indexes(len(nodes))

    # --- Build a quick node-id→doc lookup for edge keyword/description derivation ---
    from reason_mcp.knowledge.arango_client import get_graph_db

    _db = get_graph_db()
    _node_docs: dict[str, dict[str, Any]] = {}
    for node in nodes:
        _node_docs[node["node_id"]] = node

    # --- Upsert edges (with embeddings and keywords) ---
    print(f"\n── Upserting {len(edges)} edge(s) ──")
    for edge in edges:
        edge_id = edge.get("edge_id", f"{edge['from_node_id']}__{edge['to_node_id']}__{edge['type']}")
        from_doc = _node_docs.get(edge["from_node_id"])
        to_doc = _node_docs.get(edge["to_node_id"])

        description = _compose_edge_description(edge, from_doc, to_doc)
        keywords = _extract_edge_keywords(edge, from_doc, to_doc)
        kw_text = " ".join(keywords)

        print(f"  Embedding edge {edge_id!r} ...", end=" ", flush=True)
        embedding = _embed(description)
        keywords_embedding = _embed(kw_text)

        upsert_graph_edge({
            **edge,
            "description": description,
            "keywords": keywords,
            "embedding": embedding,
            "keywords_embedding": keywords_embedding,
        })
        print("done")

    # Refresh vector indexes again (now edges carry embeddings too)
    if edges:
        print(f"\n── Refreshing vector indexes (edges) ──")
        ensure_graph_vector_indexes()

    print(f"\n✓  Seeded {len(nodes)} node(s) and {len(edges)} edge(s) into the praxis graph.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the praxis graph database.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching ArangoDB.",
    )
    parser.add_argument(
        "--seeds-dir",
        type=Path,
        default=_REPO_ROOT / "seeds",
        help="Path to the seeds/ directory (default: repo root / seeds).",
    )
    args = parser.parse_args()

    seed(args.seeds_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
