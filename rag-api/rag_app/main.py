"""FastAPI 主入口。"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_app.api import health, ingest, search, ask, public
from rag_app.core.config import settings, validate_runtime_security
from rag_app.core.logging import setup_logging
from rag_app.demo import page as demo_page

validate_runtime_security()

# 初始化日志
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI 求职知识库 RAG API",
    description="本地知识库检索与问答系统 — 三类隐私隔离索引 (kb_private / kb_internal / kb_public)",
    version="0.1.0",
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 注册路由
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(search.router)
app.include_router(ask.router)
app.include_router(public.router)
app.include_router(demo_page.router)

# 索引统计接口
from fastapi import APIRouter
from rag_app.langchain_components.vector_store import get_collection_info
from rag_app.models.responses import IndexStats, IndexStatsResponse

stats_router = APIRouter()


@stats_router.get("/index/stats", response_model=IndexStatsResponse)
async def index_stats():
    yaml = settings.yaml_config
    cols = yaml.get("collections", {})
    stats_list = []
    for name in cols.values():
        info = get_collection_info(name)
        stats_list.append(IndexStats(
            collection_name=name,
            document_count=info.get("points_count", 0),
            chunk_count=info.get("points_count", 0),
            last_build=None,
            error_count=0 if "error" not in info else 1,
        ))
    return IndexStatsResponse(collections=stats_list)


app.include_router(stats_router)


@app.on_event("startup")
async def startup():
    host = settings.demo_host if settings.rag_runtime_mode == "offline_demo" else settings.api_host
    port = settings.demo_port if settings.rag_runtime_mode == "offline_demo" else settings.api_port
    logger.info(f"RAG API starting mode={settings.rag_runtime_mode} host={host} port={port}")
    logger.info(f"KB_ROOT={settings.kb_root}")
    logger.info(f"RAG_DATA_DIR={settings.rag_data_dir}")
    logger.info(f"QDRANT_PATH={settings.qdrant_path}")


def main():
    import uvicorn
    validate_runtime_security()
    host = settings.demo_host if settings.rag_runtime_mode == "offline_demo" else settings.api_host
    port = settings.demo_port if settings.rag_runtime_mode == "offline_demo" else settings.api_port
    uvicorn.run(
        "rag_app.main:app",
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
