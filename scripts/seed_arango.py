#!/usr/bin/env python
"""Seed ArangoDB with rules (and edges) from JSON knowledge files.

Reads every ``rules/*.json`` and ``edges/*.json`` file from a knowledge
directory, generates embeddings for each document using the local
SentenceTransformer model, and upserts them into ArangoDB.  Runs are
idempotent — re-running with the same input overwrites existing documents.

Usage::

    # Default knowledge dir (./knowledge/example)
    python scripts/seed_arango.py

    # Custom knowledge dir
    python scripts/seed_arango.py --knowledge-dir /path/to/knowledge

    # Dry run: print what would be seeded without writing to ArangoDB
    python scripts/seed_arango.py --dry-run

Prerequisites:
  - ArangoDB is running and reachable (configure via .env or env vars)
  - The semantic extras are installed:
      pip install "reason-mcp[semantic]"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the src package is importable when running the script directly
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402 (after sys.path fix)

load_dotenv()


def _read_json(path: Path) -> list[dict]:
    """Read a JSON file that is either a list or a ``{"rules": [...]}`` dict."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # Support {"rules": [...]} and {"edges": [...]} wrappers
        return raw.get("rules", raw.get("edges", [raw]))
    return []


def _load_rules(knowledge_dir: Path) -> list[dict]:
    rules_dir = knowledge_dir / "rules"
    if not rules_dir.exists():
        print(f"[WARNING] rules directory not found: {rules_dir}")
        return []
    rules: list[dict] = []
    for path in sorted(rules_dir.glob("*.json")):
        items = _read_json(path)
        rules.extend(items)
        print(f"  Loaded {len(items)} rules from {path.name}")
    return rules


def _load_edges(knowledge_dir: Path) -> list[dict]:
    edges_dir = knowledge_dir / "edges"
    if not edges_dir.exists():
        return []
    edges: list[dict] = []
    for path in sorted(edges_dir.glob("*.json")):
        items = _read_json(path)
        edges.extend(items)
        print(f"  Loaded {len(items)} edges from {path.name}")
    return edges


def seed(knowledge_dir: Path, dry_run: bool = False) -> None:
    """Seed ArangoDB from *knowledge_dir*.

    Args:
        knowledge_dir: Directory containing ``rules/*.json`` (and optionally
                       ``edges/*.json``).
        dry_run:       When True, perform all processing (including embedding
                       generation) but skip writes to ArangoDB.
    """
    print(f"\n=== reason-mcp seed script ===")
    print(f"Knowledge dir : {knowledge_dir}")
    print(f"Dry run       : {dry_run}")

    # -------------------------------------------------------------------------
    # Step 1 — Load rules and edges from JSON files
    # -------------------------------------------------------------------------
    print("\n[1/4] Loading JSON knowledge files…")
    rules = _load_rules(knowledge_dir)
    edges = _load_edges(knowledge_dir)

    active_rules = [r for r in rules if r.get("active", True)]
    print(f"  {len(active_rules)} active rules, {len(edges)} edges to seed")
    if not active_rules:
        print("[WARNING] No active rules found — nothing to seed.")
        return

    # -------------------------------------------------------------------------
    # Step 2 — Generate embeddings
    # -------------------------------------------------------------------------
    print("\n[2/4] Generating embeddings…")
    try:
        from reason_mcp.tools.reasoning.embedder import embed_edge, embed_rule
    except ImportError:
        print(
            "[ERROR] sentence-transformers is required for embedding generation.\n"
            "        Install it with:  pip install 'reason-mcp[semantic]'"
        )
        sys.exit(1)

    for rule in active_rules:
        rule["embedding"] = embed_rule(rule)

    for edge in edges:
        edge["embedding"] = embed_edge(edge)

    print(f"  Done: {len(active_rules)} rule embeddings, {len(edges)} edge embeddings")

    if dry_run:
        print("\n[DRY RUN] Skipping ArangoDB writes.")
        for rule in active_rules:
            emb = rule.pop("embedding")
            print(f"  rule [{rule.get('rule_id')}] embedding dim={len(emb)}")
            rule["embedding"] = emb
        print("\nDry run complete — no data written.")
        return

    # -------------------------------------------------------------------------
    # Step 3 — Ensure schema (collections + vector index)
    # -------------------------------------------------------------------------
    print("\n[3/4] Ensuring ArangoDB schema…")
    from reason_mcp.knowledge.arango_client import ensure_collections

    ensure_collections()
    print("  Collections and indexes verified/created.")

    # -------------------------------------------------------------------------
    # Step 4 — Upsert rules and edges
    # -------------------------------------------------------------------------
    print("\n[4/4] Upserting documents…")
    from reason_mcp.knowledge.arango_client import upsert_edge, upsert_rule

    seeded = 0
    for rule in active_rules:
        upsert_rule(rule)
        seeded += 1

    print(f"  Upserted {seeded} rules.")

    edge_seeded = 0
    for edge in edges:
        try:
            upsert_edge(edge)
            edge_seeded += 1
        except Exception as exc:
            print(f"  [WARNING] Failed to upsert edge {edge}: {exc}")

    print(f"  Upserted {edge_seeded} edges.")
    print(f"\nSeed complete: {seeded} rules, {edge_seeded} edges written to ArangoDB.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed ArangoDB with knowledge rules from JSON files."
    )
    parser.add_argument(
        "--knowledge-dir",
        default=str(_REPO_ROOT / "knowledge" / "example"),
        help="Path to the knowledge directory containing rules/ and edges/ subfolders.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process and embed rules but skip writing to ArangoDB.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    seed(Path(args.knowledge_dir), dry_run=args.dry_run)
