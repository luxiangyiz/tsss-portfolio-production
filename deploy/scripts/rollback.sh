#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

TARGET_VERSION="${1:-}"
if [ -z "$TARGET_VERSION" ]; then
    TARGET_VERSION="$(git -C "$PROJECT_ROOT" log --skip=1 -1 --format='%H')"
fi
TARGET_SHA="$(git -C "$PROJECT_ROOT" rev-parse "${TARGET_VERSION}^{commit}")"
CURRENT_SHA="$(git -C "$PROJECT_ROOT" rev-parse HEAD)"

echo "[ROLLBACK] Current: $CURRENT_SHA"
echo "[ROLLBACK] Target:  $TARGET_SHA"
read -r -p "Type YES to continue: " CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    echo "[ROLLBACK] Cancelled"
    exit 0
fi

require_clean_repository
"$SCRIPT_DIR/backup.sh"
git -C "$PROJECT_ROOT" fetch --prune origin
git -C "$PROJECT_ROOT" checkout --detach "$TARGET_SHA"
require_clean_repository

compose config --quiet
compose build rag-api rag-index
compose up -d --remove-orphans mysql wordpress rag-api nginx

for _ in $(seq 1 24); do
    if compose exec -T nginx wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 \
        && compose exec -T rag-api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/public/health/live', timeout=5).read()" >/dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d_%H%M%S') | rollback | $CURRENT_SHA | $TARGET_SHA" \
            >> "$PROJECT_ROOT/logs/deploy_record.txt"
        echo "[ROLLBACK] Completed"
        exit 0
    fi
    sleep 5
done

compose ps
compose logs --tail=100
echo "[ERROR] Rollback target failed health checks" >&2
exit 1
