#!/usr/bin/env python
"""Seed ArangoDB with rules and edges from the ``seeds/`` Python package.

Rule data is defined as plain Python dicts in ``seeds/<domain>.py`` modules.
Import :data:`seeds.RULES` and :data:`seeds.EDGES` to access the full data set.

Usage::

    # Seed from the built-in seeds/ package (default)
    python scripts/seed_arango.py

    # Preview embeddings and DB writes without touching ArangoDB
    python scripts/seed_arango.py --dry-run

    # Seed from legacy JSON knowledge files (backward-compat override)
    python scripts/seed_arango.py --knowledge-dir /path/to/knowledge

Prerequisites:
  - ArangoDB is running and reachable (configure via .env or env vars)
  - Semantic extras are installed:
      pip install "reason-mcp[semantic]"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure both the src package and seeds package are importable when run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()


# ---------------------------------------------------------------------------
# Data loading — seeds package (default) or JSON knowledge dir (override)
# ---------------------------------------------------------------------------


def _load_from_seeds() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load rules and edges from the built-in ``seeds/`` Python package."""
    try:
        import seeds  # type: ignore  # noqa: PLC0415
    except ImportError as exc:
        print(
            f"[ERROR] Could not import 'seeds' package: {exc}\n"
            f"        Make sure you run this script from the repository root."
        )
        sys.exit(1)

    rules = [r for r in seeds.RULES if r.get("active", True)]
    edges = list(seeds.EDGES)
    return rules, edges


def _read_json(path: Path) -> list[dict[str, Any]]:
    """Read a JSON file that is either a list or a dict wrapper."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("rules", raw.get("edges", [raw]))
    return []


def _load_from_knowledge_dir(
    knowledge_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load rules and edges from JSON files in a knowledge directory."""
    rules: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    rules_dir = knowledge_dir / "rules"
    if rules_dir.exists():
        for path in sorted(rules_dir.glob("*.json")):
            items = _read_json(path)
            rules.extend(items)
            print(f"  Loaded {len(items)} rules from {path.name}")
    else:
        print(f"[WARNING] rules/ directory not found: {rules_dir}")

    edges_dir = knowledge_dir / "edges"
    if edges_dir.exists():
        for path in sorted(edges_dir.glob("*.json")):
            items = _read_json(path)
            edges.extend(items)
            print(f"  Loaded {len(items)} edges from {path.name}")

    active = [r for r in rules if r.get("active", True)]
    return active, edges


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------


def seed(
    rules: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    dry_run: bool = False,
) -> None:
    """Generate embeddings for *rules* and *edges*, then upsert into ArangoDB."""
    print(f"  {len(rules)} active rules, {len(edges)} edges to seed")
    if not rules:
        print("[WARNING] No active rules found — nothing to seed.")
        return

    # Step 2 — Generate embeddings
    print("\n[2/4] Generating embeddings…")
    try:
        from reason_mcp.tools.reasoning.embedder import embed_edge, embed_rule
    except ImportError:
        print(
            "[ERROR] sentence-transformers is required for embedding generation.\n"
            "        Install it with:  pip install 'reason-mcp[semantic]'"
        )
        sys.exit(1)

    for rule in rules:
        rule["embedding"] = embed_rule(rule)

    for edge in edges:
        edge["embedding"] = embed_edge(edge)

    print(f"  Done: {len(rules)} rule embeddings, {len(edges)} edge embeddings")

    if dry_run:
        print("\n[DRY RUN] Skipping ArangoDB writes.")
        for rule in rules:
            emb = rule.pop("embedding")
            print(f"  rule [{rule.get('rule_id')}] embedding dim={len(emb)}")
            rule["embedding"] = emb
        print("\nDry run complete — no data written.")
        return

    # Step 3 — Ensure schema (collections + persistent indexes only).
    # The vector index is created in step 4b, AFTER documents are upserted,
    # because ArangoDB trains the index on existing embedding data.
    print("\n[3/4] Ensuring ArangoDB schema…")
    from reason_mcp.knowledge.arango_client import (
        ensure_collections,
        ensure_vector_index,
        upsert_edge,
        upsert_rule,
    )

    ensure_collections()
    print("  Collections and indexes verified/created.")

    # Step 4 — Upsert documents, then build vector index.
    print("\n[4/4] Upserting documents…")
    for rule in rules:
        upsert_rule(rule)
    print(f"  Upserted {len(rules)} rules.")

    edge_errors = 0
    for edge in edges:
        try:
            upsert_edge(edge)
        except Exception as exc:
            print(f"  [WARNING] Failed to upsert edge {edge}: {exc}")
            edge_errors += 1

    seeded_edges = len(edges) - edge_errors
    print(f"  Upserted {seeded_edges} edges.")

    # Build vector index after data is in place (ArangoDB requirement).
    print("  Building vector index…")
    ensure_vector_index(n_docs=len(rules))
    print(f"\nSeed complete: {len(rules)} rules, {seeded_edges} edges written to ArangoDB.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Seed ArangoDB with domain knowledge rules.\n"
            "By default, rules are loaded from the built-in 'seeds/' Python package."
        )
    )
    parser.add_argument(
        "--knowledge-dir",
        default=None,
        help=(
            "Path to a legacy JSON knowledge directory (rules/ + edges/ subfolders).  "
            "When omitted, the seeds/ Python package is used instead."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process and embed rules but skip writing to ArangoDB.",
    )
    args = parser.parse_args()

    print("\n=== reason-mcp seed script ===")

    print("\n[1/4] Loading knowledge…")
    if args.knowledge_dir:
        kdir = Path(args.knowledge_dir)
        print(f"  Source: JSON knowledge dir — {kdir}")
        rules, edges = _load_from_knowledge_dir(kdir)
    else:
        print("  Source: seeds/ Python package")
        rules, edges = _load_from_seeds()
        # Print module summary
        try:
            import seeds  # type: ignore  # noqa: PLC0415
            import importlib, pkgutil

            for _finder, modname, _ispkg in pkgutil.iter_modules(seeds.__path__):
                mod = importlib.import_module(f"seeds.{modname}")
                r_count = len(getattr(mod, "RULES", []))
                e_count = len(getattr(mod, "EDGES", []))
                print(f"  seeds/{modname}.py — {r_count} rules, {e_count} edges")
        except Exception:
            pass

    print(f"  Dry run: {args.dry_run}")
    seed(rules, edges, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

