#!/bin/bash
# ============================================================
# 备份脚本 — 备份 MySQL、uploads、Qdrant 数据和内容清单
# 建议每日运行（cron），保留 7 份日备份和 4 份周备份
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.production.yml"
ENV_FILE="$DEPLOY_DIR/.env.production"
BACKUP_ROOT="${BACKUP_ROOT:-$PROJECT_ROOT/backups}"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[BACKUP]${NC} $*"; }
err() { echo -e "${RED}[ERROR]${NC} $*"; }

log "============================================"
log "备份开始 — $TIMESTAMP"
log "============================================"

mkdir -p "$BACKUP_DIR"

# --- MySQL 备份 ---
log "备份 MySQL..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T mysql \
    mysqldump -u root -p"${MYSQL_ROOT_PASSWORD}" --all-databases \
    --single-transaction --quick --lock-tables=false \
    > "$BACKUP_DIR/mysql_dump.sql" 2>/dev/null

if [ -s "$BACKUP_DIR/mysql_dump.sql" ]; then
    log "MySQL 备份完成: $(wc -c < "$BACKUP_DIR/mysql_dump.sql") 字节"
else
    err "MySQL 备份失败"
    exit 1
fi

# --- WordPress uploads 备份 ---
log "备份 WordPress uploads..."
mkdir -p "$BACKUP_DIR/uploads"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T wordpress \
    tar czf - -C /var/www/html/wp-content/uploads . 2>/dev/null \
    > "$BACKUP_DIR/uploads.tar.gz" || log "uploads 备份跳过（可能为空）"

# --- Qdrant 备份 ---
log "备份 Qdrant 公开索引..."
QDRANT_SNAPSHOT=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T qdrant \
    curl -s -X POST http://localhost:6333/collections/kb_public/snapshots 2>/dev/null || echo "")
if [ -n "$QDRANT_SNAPSHOT" ]; then
    log "Qdrant 快照请求已发送"
else
    log "Qdrant 快照跳过（集合可能为空）"
fi

# --- 内容清单备份 ---
log "备份公开内容清单..."
cp "$PROJECT_ROOT/manifests/public-source-manifest.json" "$BACKUP_DIR/"

# --- 部署记录备份 ---
if [ -f "$PROJECT_ROOT/logs/deploy_record.txt" ]; then
    cp "$PROJECT_ROOT/logs/deploy_record.txt" "$BACKUP_DIR/"
fi

# --- 当前版本信息 ---
CURRENT_SHA=$(cd "$PROJECT_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")
echo "commit_sha: $CURRENT_SHA" > "$BACKUP_DIR/deploy_version.txt"
echo "backup_time: $TIMESTAMP" >> "$BACKUP_DIR/deploy_version.txt"

# --- 打包 ---
log "打包备份..."
BACKUP_ARCHIVE="$BACKUP_ROOT/backup_${TIMESTAMP}.tar.gz"
tar czf "$BACKUP_ARCHIVE" -C "$BACKUP_ROOT" "$TIMESTAMP"
rm -rf "$BACKUP_DIR"

log "备份归档: $BACKUP_ARCHIVE ($(du -h "$BACKUP_ARCHIVE" | cut -f1))"

# --- 清理旧备份 ---
log "清理旧备份（保留 7 份日备份）..."
ls -t "$BACKUP_ROOT"/backup_*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

log "============================================"
log "备份完成"
log "============================================"
