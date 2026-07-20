#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

VERSION="${1:-origin/main}"
TIMESTAMP="$(date '+%Y-%m-%d_%H%M%S')"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/deploy_${TIMESTAMP}.log"
DEPLOY_RECORD="$LOG_DIR/deploy_record.txt"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[DEPLOY] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

require_command docker
require_command git
docker compose version >/dev/null
require_clean_repository

log "Fetching target version: $VERSION"
git -C "$PROJECT_ROOT" fetch --prune origin
TARGET_SHA="$(git -C "$PROJECT_ROOT" rev-parse "${VERSION}^{commit}")"

if compose ps --status running --services 2>/dev/null | grep -qx mysql; then
    log "Creating pre-deploy backup"
    "$SCRIPT_DIR/backup.sh"
fi

git -C "$PROJECT_ROOT" checkout --detach "$TARGET_SHA"
require_clean_repository
log "Deploying commit: $TARGET_SHA"

compose config --quiet

log "Building RAG image"
compose build --pull rag-api rag-index

log "Starting production services"
compose up -d --remove-orphans mysql wordpress rag-api nginx

log "Waiting for health checks"
READY=false
for _ in $(seq 1 24); do
    if compose exec -T nginx wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 \
        && compose exec -T rag-api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/public/health/live', timeout=5).read()" >/dev/null 2>&1 \
        && compose exec -T wordpress php-fpm -t >/dev/null 2>&1 \
        && compose exec -T mysql sh -c 'mysqladmin ping -h 127.0.0.1 -u root -p"$MYSQL_ROOT_PASSWORD" --silent' >/dev/null 2>&1; then
        READY=true
        break
    fi
    sleep 5
done

if [ "$READY" != "true" ]; then
    compose ps
    compose logs --tail=100
    echo "$TIMESTAMP | $VERSION | $TARGET_SHA | failed-health" >> "$DEPLOY_RECORD"
    fail "Production services did not become healthy within 120 seconds"
fi

log "Running local smoke tests"
compose exec -T nginx wget -qO- http://127.0.0.1/healthz >/dev/null
compose exec -T rag-api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/public/health/live', timeout=5).read()" \
    >/dev/null

echo "$TIMESTAMP | $VERSION | $TARGET_SHA | deployed" >> "$DEPLOY_RECORD"
log "Deployment completed: $TARGET_SHA"
log "Log: $LOG_FILE"
