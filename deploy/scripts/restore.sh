#!/bin/bash
# ============================================================
# 恢复脚本 — 从备份归档恢复站点
# 用法: ./restore.sh <backup_file.tar.gz>
# 警告：数据恢复是高风险操作，会覆盖当前数据！
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.production.yml"
ENV_FILE="$DEPLOY_DIR/.env.production"

BACKUP_FILE="${1:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[RESTORE]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

if [ -z "$BACKUP_FILE" ]; then
    err "用法: $0 <backup_file.tar.gz>"
    err "可用备份:"
    ls -lh "$PROJECT_ROOT/backups"/backup_*.tar.gz 2>/dev/null || echo "  (无)"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    err "备份文件不存在: $BACKUP_FILE"
    exit 1
fi

echo ""
warn "================================================"
warn " 警告：数据恢复将覆盖当前 MySQL/WordPress 数据！"
warn " 备份文件: $BACKUP_FILE"
warn "================================================"
echo ""
read -p "确认恢复？输入 YES 继续: " CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    log "恢复已取消"
    exit 0
fi

TEMP_DIR=$(mktemp -d)
log "解压备份到临时目录: $TEMP_DIR"
tar xzf "$BACKUP_FILE" -C "$TEMP_DIR"
BACKUP_DIR=$(ls -d "$TEMP_DIR"/*/)

# --- 先备份当前现场 ---
log "备份当前现场..."
"$SCRIPT_DIR/backup.sh"

# --- 停止写入 ---
log "暂停外部访问..."
# （可根据需要添加维护页面逻辑）

# --- 恢复 MySQL ---
if [ -f "$BACKUP_DIR/mysql_dump.sql" ]; then
    log "恢复 MySQL..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T mysql \
        mysql -u root -p"${MYSQL_ROOT_PASSWORD}" < "$BACKUP_DIR/mysql_dump.sql"
    log "MySQL 恢复完成"
fi

# --- 恢复 uploads ---
if [ -f "$BACKUP_DIR/uploads.tar.gz" ]; then
    log "恢复 WordPress uploads..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T wordpress \
        tar xzf - -C /var/www/html/wp-content/uploads < "$BACKUP_DIR/uploads.tar.gz"
    log "uploads 恢复完成"
fi

# --- 刷新 WordPress 缓存 ---
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T wordpress \
    wp cache flush --allow-root 2>/dev/null || true

# --- 清理 ---
rm -rf "$TEMP_DIR"

log "============================================"
log "恢复完成 — 请执行冒烟测试验证"
log "============================================"
