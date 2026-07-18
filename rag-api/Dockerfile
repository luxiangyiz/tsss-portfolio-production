# ============================================================
# 公开 RAG API — 最小化生产 Dockerfile
# 仅启动 rag_app.public_main:app，不暴露内部接口
# ============================================================

FROM python:3.13-slim

LABEL app="zwd-portfolio-rag-api"
LABEL description="Public-only RAG API for personal website"
LABEL version="0.1.0"

# 安全：以非 root 用户运行
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码（只包含公开入口需要的部分）
COPY rag_app/ rag_app/

# 复制公开生产配置到 config.py 默认加载路径
# config.py 从 <package>/../../../../configs/rag_config.yaml 加载，
# 容器内 rag_app 位于 /app/rag_app/，因此加载路径为 /app/configs/rag_config.yaml
COPY configs/rag_config.public.yaml configs/rag_config.yaml

# 创建非 root 用户可写目录
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser

# 健康检查 — 仅调用公开端点
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/rag/public/health || exit 1

# 固定启动公开入口，不开放文档和内部路由
EXPOSE 8000

CMD ["uvicorn", "rag_app.public_main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "warning", "--no-access-log"]
