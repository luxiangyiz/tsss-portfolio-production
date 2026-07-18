"""Retriever — 封装 Qdrant 检索，返回带分数的 Document。"""

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from rag_app.langchain_components.vector_store import get_client


def retrieve_with_scores(
    collection_name: str,
    query: str,
    embeddings,
    top_k: int = 5,
) -> list[tuple[Document, float]]:
    """检索并返回 (Document, score)。"""
    from langchain_qdrant import QdrantVectorStore

    vector_store = QdrantVectorStore(
        client=get_client(),
        collection_name=collection_name,
        embedding=embeddings,
    )
    return vector_store.similarity_search_with_score(query, k=top_k)
