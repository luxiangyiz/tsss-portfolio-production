"""Embeddings 工厂 — 创建 LangChain Embeddings 实例。"""

from langchain_openai import OpenAIEmbeddings

from rag_app.core.config import get_default_embedding_kwargs, settings


def create_embeddings():
    if settings.rag_runtime_mode == "offline_demo":
        if not settings.allow_fake_mode:
            raise RuntimeError("Fake embeddings are disabled")
        from rag_app.demo.dependencies import create_demo_embeddings

        return create_demo_embeddings(settings.embedding_dimension)

    kwargs = get_default_embedding_kwargs()
    return OpenAIEmbeddings(**kwargs)
