"""健康检查接口。"""

from fastapi import APIRouter

from rag_app.langchain_components.vector_store import get_client, get_collection_info
from rag_app.core.config import settings
from rag_app.models.responses import HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
async def health_check():
    yaml = settings.yaml_config
    cols = yaml.get("collections", {})

    collections_info = {}
    qdrant_status = "ok"
    for name in cols.values():
        info = get_collection_info(name)
        collections_info[name] = {
            "points_count": info.get("points_count", 0),
            "status": "ok" if "error" not in info else info["error"],
        }
        if "error" in info:
            qdrant_status = "degraded"

    # 检查 embedding 可用性
    embedding_status = "ok"
    try:
        from rag_app.langchain_components.embeddings import create_embeddings
        emb = create_embeddings()
        emb.embed_query("test")
    except Exception:
        embedding_status = "unavailable"

    # 检查 LLM 可用性
    llm_status = "ok"
    try:
        from rag_app.langchain_components.chat_model import create_chat_model
        llm = create_chat_model()
        llm.invoke("hi")
    except Exception:
        llm_status = "unavailable"

    offline = settings.rag_runtime_mode == "offline_demo"
    limitations = []
    if offline:
        limitations = [
            "确定性Fake Embedding不代表真实语义检索质量",
            "FakeChatModel不代表真实LLM回答与拒答质量",
            "仅用于本地工程链路和隐私边界演示",
        ]

    return HealthStatus(
        status="ok" if qdrant_status == "ok" and embedding_status == "ok" and llm_status == "ok" else "degraded",
        qdrant=qdrant_status,
        embedding=embedding_status,
        llm=llm_status,
        collections=collections_info,
        runtime_mode=settings.rag_runtime_mode,
        runtime_label="OFFLINE DEMO" if offline else "REAL LOCAL",
        embedding_model="demo-deterministic-ngram" if offline else settings.embedding_model,
        llm_model="demo-fake-chat" if offline else settings.llm_model,
        local_only=True,
        limitations=limitations,
    )
