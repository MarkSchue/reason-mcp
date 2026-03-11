#!/usr/bin/env bash
# start_arango.sh — Start ArangoDB with the vector-index feature enabled.
#
# Usage:
#   ./scripts/start_arango.sh           # foreground (logs to stdout)
#   ./scripts/start_arango.sh -d        # detached / background
#
# Requirements: Docker (https://docs.docker.com/get-docker/)
#
# Data is persisted in a named Docker volume "reason-arango-data" so the DB
# survives container restarts.  The volume is created automatically on first run.
#
# After first start, seed the rules:
#   python scripts/seed_arango.py
#
# To stop the container:
#   docker stop reason-arango
#
# To remove it (keeps volume / data):
#   docker rm reason-arango
#
# To wipe data completely:
#   docker rm reason-arango && docker volume rm reason-arango-data

set -euo pipefail

CONTAINER_NAME="reason-arango"
ARANGO_IMAGE="arangodb:3.12"
ARANGO_VOLUME="reason-arango-data"
ARANGO_PORT="8529"

# Load credentials from .env if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [[ -f "${ENV_FILE}" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${ENV_FILE}"; set +a
fi

ARANGO_ROOT_PASSWORD="${REASON_ARANGO_PASSWORD:-}"
if [[ -z "${ARANGO_ROOT_PASSWORD}" ]]; then
    echo "[ERROR] REASON_ARANGO_PASSWORD is not set."
    echo "        Set it in .env or export it before running this script."
    exit 1
fi

# Detached flag
DETACH_FLAG=""
if [[ "${1:-}" == "-d" ]]; then
    DETACH_FLAG="--detach"
    echo "Starting ArangoDB in background…"
else
    echo "Starting ArangoDB in foreground (Ctrl-C to stop)…"
    echo "Tip: run with -d to start detached."
    echo ""
fi

# Remove a stopped container with the same name (ignore errors if not present)
docker rm --force "${CONTAINER_NAME}" 2>/dev/null || true

docker run \
    --name "${CONTAINER_NAME}" \
    ${DETACH_FLAG} \
    --publish "${ARANGO_PORT}:8529" \
    --volume "${ARANGO_VOLUME}:/var/lib/arangodb3" \
    --env "ARANGO_ROOT_PASSWORD=${ARANGO_ROOT_PASSWORD}" \
    "${ARANGO_IMAGE}" \
    arangod \
        --server.endpoint "tcp://0.0.0.0:8529" \
        --vector-index true

# When running detached, wait for the HTTP port to be ready
if [[ -n "${DETACH_FLAG}" ]]; then
    echo ""
    echo -n "Waiting for ArangoDB to be ready"
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:${ARANGO_PORT}/_api/version" -u "root:${ARANGO_ROOT_PASSWORD}" > /dev/null 2>&1; then
            echo " ready."
            echo ""
            echo "ArangoDB is up at http://localhost:${ARANGO_PORT}"
            echo "  Web UI:   http://localhost:${ARANGO_PORT}/_db/_system"
            echo "  Seed:     python scripts/seed_arango.py"
            echo "  Stop:     docker stop ${CONTAINER_NAME}"
            exit 0
        fi
        echo -n "."
        sleep 1
    done
    echo " timed out."
    echo "[WARNING] ArangoDB may still be starting — check: docker logs ${CONTAINER_NAME}"
fi
