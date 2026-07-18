#!/bin/bash
# ============================================================
# 回滚脚本 — 回滚应用代码到上一可用版本
# 不执行数据库降级，除非该版本包含不可兼容的数据迁移
# 用法: ./rollback.sh [COMMIT_SHA]
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.production.yml"
ENV_FILE="$DEPLOY_DIR/.env.production"

TARGET_VERSION="${1:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[ROLLBACK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# --- 记录故障现场 ---
CURRENT_SHA=$(cd "$PROJECT_ROOT" && git rev-parse HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date '+%Y-%m-%d_%H%M%S')

log "============================================"
log "回滚开始 — $TIMESTAMP"
log "当前版本: $CURRENT_SHA"
log "============================================"

# --- 确定回滚目标 ---
if [ -z "$TARGET_VERSION" ]; then
    # 获取上一个部署版本
    DEPLOY_RECORD="$PROJECT_ROOT/logs/deploy_record.txt"
    if [ -f "$DEPLOY_RECORD" ]; then
        TARGET_VERSION=$(tail -2 "$DEPLOY_RECORD" | head -1 | awk '{print $3}')
    fi
    if [ -z "$TARGET_VERSION" ]; then
        # 使用上一个 Git 提交
        TARGET_VERSION=$(cd "$PROJECT_ROOT" && git log --skip=1 -1 --format='%H' 2>/dev/null || echo "")
    fi
fi

if [ -z "$TARGET_VERSION" ]; then
    err "无法确定回滚目标版本"
    exit 1
fi

log "回滚目标: $TARGET_VERSION"

# --- 确认 ---
echo ""
warn "================================================"
warn " 回滚将切换应用代码到版本: $TARGET_VERSION"
warn " 数据库不会被降级"
warn "================================================"
echo ""
read -p "确认回滚？输入 YES 继续: " CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    log "回滚已取消"
    exit 0
fi

# --- 记录故障 ---
echo "$TIMESTAMP | rollback | $CURRENT_SHA → $TARGET_VERSION" >> "$PROJECT_ROOT/logs/deploy_record.txt"

# --- 执行回滚 ---
log "切换 Git 版本..."
cd "$PROJECT_ROOT"
git fetch origin
git checkout "$TARGET_VERSION"

# --- 重新部署 ---
log "重新部署容器..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

sleep 10

# --- 冒烟测试 ---
log "冒烟测试..."

if curl -sf -o /dev/null http://localhost/api/rag/public/health; then
    log "RAG 健康检查: 通过"
else
    warn "RAG 健康检查: 失败"
fi

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    log "WordPress 首页: HTTP $HTTP_CODE — 通过"
else
    warn "WordPress 首页: HTTP $HTTP_CODE — 需检查"
fi

log "============================================"
log "回滚完成 — 当前版本: $(git rev-parse HEAD)"
log "============================================"
