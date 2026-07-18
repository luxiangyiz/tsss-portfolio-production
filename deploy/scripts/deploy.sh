#!/bin/bash
# ============================================================
# 生产部署脚本 — deploy.sh
# 用法: ./deploy.sh [VERSION]
#   VERSION: Git commit SHA 或 tag，默认使用 main 最新提交
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.production.yml"
ENV_FILE="$DEPLOY_DIR/.env.production"

VERSION="${1:-main}"
TIMESTAMP=$(date '+%Y-%m-%d_%H%M%S')
LOG_FILE="$PROJECT_ROOT/logs/deploy_${TIMESTAMP}.log"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*" | tee -a "$LOG_FILE"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"; }

mkdir -p "$(dirname "$LOG_FILE")"

log "============================================"
log "部署开始 — 版本: $VERSION — $TIMESTAMP"
log "============================================"

# --- 前置检查 ---
log "检查前置条件..."

if ! command -v docker &>/dev/null; then
    err "Docker 未安装"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    err "Docker Compose 插件未安装"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    err "环境文件不存在: $ENV_FILE"
    err "请从 production.env.example 复制并填入实际值"
    exit 1
fi

# --- 拉取指定版本 ---
log "切换 Git 版本: $VERSION"
cd "$PROJECT_ROOT"
git fetch origin
git checkout "$VERSION"
COMMIT_SHA=$(git rev-parse HEAD)
log "当前 Commit: $COMMIT_SHA"

# --- 验证 Compose 配置 ---
log "验证 Docker Compose 配置..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config -q
if [ $? -ne 0 ]; then
    err "Compose 配置验证失败"
    exit 1
fi
log "Compose 配置验证通过"

# --- 构建镜像 ---
log "构建 RAG API 镜像..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --pull rag-api

# --- 部署 ---
log "启动/更新容器..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

# --- 等待健康检查 ---
log "等待服务就绪..."
sleep 10
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    UNHEALTHY=$(docker compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null | \
        python3 -c "import sys,json; [print(json.loads(l)['Name']) for l in sys.stdin if l.strip() and json.loads(l).get('Health') not in ('healthy','')]" 2>/dev/null || true)
    if [ -z "$UNHEALTHY" ]; then
        log "所有服务健康检查通过"
        break
    fi
    sleep 10
    WAITED=$((WAITED + 10))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    warn "部分服务健康检查超时，请手动检查"
fi

# --- 冒烟测试 ---
log "执行冒烟测试..."

# 测试 RAG 健康检查
if curl -sf -o /dev/null http://localhost/api/rag/public/health; then
    log "RAG 健康检查: 通过"
else
    warn "RAG 健康检查: 失败"
fi

# 测试 WordPress 首页
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    log "WordPress 首页: HTTP $HTTP_CODE — 通过"
else
    warn "WordPress 首页: HTTP $HTTP_CODE — 需检查"
fi

# --- 记录部署信息 ---
DEPLOY_RECORD="$PROJECT_ROOT/logs/deploy_record.txt"
echo "$TIMESTAMP | $VERSION | $COMMIT_SHA | deployed" >> "$DEPLOY_RECORD"

log "============================================"
log "部署完成 — Commit: $COMMIT_SHA"
log "日志: $LOG_FILE"
log "============================================"
