#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
require_command tar

BACKUP_ROOT="${BACKUP_ROOT:-$PROJECT_ROOT/backups}"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
WORK_DIR="$BACKUP_ROOT/.work_$TIMESTAMP"
BACKUP_ARCHIVE="$BACKUP_ROOT/backup_${TIMESTAMP}.tar.gz"
RAG_WAS_RUNNING=false

cleanup() {
    rm -rf "$WORK_DIR"
    if [ "$RAG_WAS_RUNNING" = "true" ]; then
        compose up -d rag-api >/dev/null
    fi
}
trap cleanup EXIT

mkdir -p "$WORK_DIR"
chmod 700 "$BACKUP_ROOT" "$WORK_DIR"

echo "[BACKUP] Dumping MySQL"
compose exec -T mysql sh -c \
    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -u root --all-databases --single-transaction --quick --skip-lock-tables' \
    > "$WORK_DIR/mysql_dump.sql"
test -s "$WORK_DIR/mysql_dump.sql"

echo "[BACKUP] Archiving WordPress uploads"
compose exec -T wordpress sh -c \
    'mkdir -p /var/www/html/wp-content/uploads && tar czf - -C /var/www/html/wp-content/uploads .' \
    > "$WORK_DIR/uploads.tar.gz"
tar tzf "$WORK_DIR/uploads.tar.gz" >/dev/null

if compose ps --status running --services | grep -qx rag-api; then
    RAG_WAS_RUNNING=true
    compose stop rag-api >/dev/null
fi

echo "[BACKUP] Archiving embedded Qdrant data"
docker run --rm \
    -v zwd_rag_data:/source:ro \
    -v "$WORK_DIR:/backup" \
    alpine:3.21 \
    tar czf /backup/rag_data.tar.gz -C /source .
tar tzf "$WORK_DIR/rag_data.tar.gz" >/dev/null

cp "$PROJECT_ROOT/manifests/source-sync-manifest.json" "$WORK_DIR/"
cp "$PROJECT_ROOT/manifests/repository-manifest.json" "$WORK_DIR/"
git -C "$PROJECT_ROOT" rev-parse HEAD > "$WORK_DIR/commit_sha.txt"
date --iso-8601=seconds > "$WORK_DIR/backup_time.txt"

tar czf "$BACKUP_ARCHIVE" -C "$WORK_DIR" .
tar tzf "$BACKUP_ARCHIVE" >/dev/null
test -s "$BACKUP_ARCHIVE"
chmod 600 "$BACKUP_ARCHIVE"

find "$BACKUP_ROOT" -maxdepth 1 -type f -name 'backup_*.tar.gz' -printf '%T@ %p\n' \
    | sort -rn \
    | tail -n +8 \
    | cut -d' ' -f2- \
    | xargs -r rm -f

echo "[BACKUP] Completed: $BACKUP_ARCHIVE"
