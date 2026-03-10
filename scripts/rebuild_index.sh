#!/usr/bin/env bash
# rebuild_index.sh — Invalidate the ChromaDB semantic index and rebuild it
# from the current knowledge rules.
#
# Usage:
#   ./scripts/rebuild_index.sh                        # uses REASON_KNOWLEDGE_DIR env var
#   ./scripts/rebuild_index.sh knowledge/example      # explicit path as first arg
#
# Run this after:
#   - Starting or restarting the MCP server
#   - Editing any rule JSON file in the knowledge directory
#   - Adding or removing rules

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Determine knowledge directory: CLI arg > env var > default
if [[ "${1:-}" != "" ]]; then
    KNOWLEDGE_DIR="${1}"
elif [[ "${REASON_KNOWLEDGE_DIR:-}" != "" ]]; then
    KNOWLEDGE_DIR="${REASON_KNOWLEDGE_DIR}"
else
    KNOWLEDGE_DIR="${WORKSPACE}/knowledge"
fi

# Resolve to absolute path
KNOWLEDGE_DIR="$(cd "${KNOWLEDGE_DIR}" && pwd)"

VENV_PYTHON="${WORKSPACE}/.venv/bin/python"
VENV_INDEX="${WORKSPACE}/.venv/bin/reason-mcp-index"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  reason-mcp: Rebuild Semantic Index"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  knowledge dir : ${KNOWLEDGE_DIR}"
echo "  index dir     : ${KNOWLEDGE_DIR}/.semantic_index"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Invalidate existing caches (JSON LRU + Chroma vectors)
echo ""
echo "▶ Step 1: Invalidating existing caches..."
export REASON_KNOWLEDGE_DIR="${KNOWLEDGE_DIR}"
"${VENV_PYTHON}" - <<'PYTHON'
import os
from pathlib import Path
from reason_mcp.knowledge.loader import invalidate_cache
invalidate_cache()
print("  ✓ JSON cache and semantic index cleared")
PYTHON

# Step 2: Rebuild the Chroma index from current rules
echo ""
echo "▶ Step 2: Rebuilding semantic index..."
export REASON_KNOWLEDGE_DIR="${KNOWLEDGE_DIR}"
export HF_HUB_VERBOSITY=error
export TRANSFORMERS_VERBOSITY=error
export TOKENIZERS_PARALLELISM=false
"${VENV_INDEX}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Index rebuild complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
