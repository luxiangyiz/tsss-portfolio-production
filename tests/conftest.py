"""全局测试配置 — 隔离测试间的全局状态污染。"""

import pytest


@pytest.fixture(autouse=True)
def isolate_global_settings():
    """保存并恢复全局 settings，防止测试间相互污染。"""
    from rag_app.core.config import settings

    saved = {
        "kb_root": settings.kb_root,
        "rag_data_dir": settings.rag_data_dir,
        "qdrant_path": settings.qdrant_path,
        "qdrant_url": settings.qdrant_url,
        "embedding_dimension": settings.embedding_dimension,
        "relevance_threshold": settings.relevance_threshold,
    }

    yield

    from rag_app.core.config import settings
    for k, v in saved.items():
        if v is not None:
            setattr(settings, k, v)

    # 重置 Qdrant client
    try:
        import rag_app.langchain_components.vector_store as vs
        if vs._client is not None:
            try:
                vs._client.close()
            except Exception:
                pass
            vs._client = None
    except Exception:
        pass

    # 重置服务单例
    for mod_path in ["rag_app.api.ingest", "rag_app.api.search", "rag_app.api.ask", "rag_app.api.public"]:
        try:
            mod = __import__(mod_path, fromlist=[""])
            for attr in ["_ingestion_service", "_search_service", "_answer_service"]:
                if hasattr(mod, attr):
                    setattr(mod, attr, None)
        except Exception:
            pass
