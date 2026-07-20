#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

MODE="${1:-incremental}"
if [ "$MODE" != "full" ] && [ "$MODE" != "incremental" ]; then
    echo "Usage: $0 [full|incremental]" >&2
    exit 1
fi

RAG_WAS_RUNNING=false
restart_rag() {
    if [ "$RAG_WAS_RUNNING" = "true" ]; then
        compose up -d rag-api >/dev/null
    fi
}
trap restart_rag EXIT

if compose ps --status running --services | grep -qx rag-api; then
    RAG_WAS_RUNNING=true
    compose stop rag-api
fi

compose --profile tools run --rm rag-index \
    index --scope public --mode "$MODE"

echo "[RAG] Public $MODE index completed"
