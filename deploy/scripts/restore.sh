#!/bin/bash

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>" >&2
    exit 1
fi

echo "[WARN] Restore overwrites MySQL, uploads and RAG data."
read -r -p "Type YES to continue: " CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    echo "[RESTORE] Cancelled"
    exit 0
fi

tar tzf "$BACKUP_FILE" >/dev/null
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT
tar xzf "$BACKUP_FILE" -C "$TEMP_DIR"

for required in mysql_dump.sql uploads.tar.gz rag_data.tar.gz commit_sha.txt; do
    test -f "$TEMP_DIR/$required" || {
        echo "[ERROR] Backup is missing $required" >&2
        exit 1
    }
done

echo "[RESTORE] Backing up current state"
"$SCRIPT_DIR/backup.sh"

echo "[RESTORE] Restoring MySQL"
compose exec -T mysql sh -c \
    'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -u root' \
    < "$TEMP_DIR/mysql_dump.sql"

echo "[RESTORE] Restoring uploads"
compose exec -T wordpress sh -c \
    'rm -rf /var/www/html/wp-content/uploads/* && tar xzf - -C /var/www/html/wp-content/uploads' \
    < "$TEMP_DIR/uploads.tar.gz"

echo "[RESTORE] Restoring embedded Qdrant data"
compose stop rag-api
docker run --rm \
    -v zwd_rag_data:/target \
    -v "$TEMP_DIR:/backup:ro" \
    alpine:3.21 \
    sh -c 'find /target -mindepth 1 -delete && tar xzf /backup/rag_data.tar.gz -C /target'
compose up -d rag-api

compose exec -T rag-api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/public/health/live', timeout=5).read()" \
    >/dev/null
echo "[RESTORE] Completed from: $BACKUP_FILE"
