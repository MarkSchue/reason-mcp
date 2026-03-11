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
            print(f"  NODE  {node['node_id']!r:45s}  type={node.get('type', '?')}")
            print(f"        embed({text[:60]!r}...)")
        for edge in edges:
            print(
                f"  EDGE  {edge.get('edge_id', '?')!r:45s}  "
                f"{edge['from_node_id']} --[{edge['type']}]--> {edge['to_node_id']}"
            )
        print("\n[DRY RUN] No changes written to ArangoDB.")
        return

    # --- Set up DB schema ---
    print("\n── Setting up ArangoDB schema (praxis) ──")
    from reason_mcp.knowledge.arango_client import ensure_graph_schema

    ensure_graph_schema()

    from reason_mcp.knowledge.arango_client import upsert_node, upsert_graph_edge

    # --- Upsert nodes (with embeddings) ---
    print(f"\n── Upserting {len(nodes)} node(s) ──")
    for node in nodes:
        node_id = node["node_id"]
        text = node.get("description", node.get("name", node_id))
        print(f"  Embedding node {node_id!r} ...", end=" ", flush=True)
        embedding = _embed(text)
        upsert_node({**node, "embedding": embedding})
        print("done")

    # --- Upsert edges ---
    print(f"\n── Upserting {len(edges)} edge(s) ──")
    for edge in edges:
        edge_id = edge.get("edge_id", f"{edge['from_node_id']}__{edge['to_node_id']}__{edge['type']}")
        print(f"  Edge {edge_id!r} ...", end=" ", flush=True)
        upsert_graph_edge(edge)
        print("done")

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
