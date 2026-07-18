"""向量存储 — Qdrant 客户端管理。存储路径: data/rag/qdrant。"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from rag_app.core.config import settings
from rag_app.knowledge.chunk_id import make_chunk_id


def _get_client() -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url)
    path = settings.qdrant_path
    return QdrantClient(path=path)


_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


def ensure_collection(collection_name: str, vector_size: int = None):
    """确保 collection 存在，维度不匹配时自动重建。"""
    if vector_size is None:
        from rag_app.core.config import settings
        vector_size = settings.embedding_dimension
    client = get_client()
    try:
        existing = client.get_collection(collection_name)
        existing_dim = existing.config.params.vectors.size
        if existing_dim != vector_size:
            client.delete_collection(collection_name)
            raise Exception("recreate")
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=vector_size,
                distance=qdrant_models.Distance.COSINE,
            ),
        )


def delete_collection(collection_name: str):
    client = get_client()
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass


def add_documents(
    collection_name: str,
    documents: list[Document],
    embeddings,
    batch_size: int = 50,
) -> list[str]:
    """将文档批量写入 Qdrant，返回成功写入的 chunk_id 列表。"""
    from langchain_qdrant import QdrantVectorStore

    ensure_collection(collection_name)

    vector_store = QdrantVectorStore(
        client=get_client(),
        collection_name=collection_name,
        embedding=embeddings,
    )

    now = datetime.now(timezone.utc).isoformat()
    uuids: list[str] = []
    chunk_ids: list[str] = []
    for doc in documents:
        doc_id = doc.metadata.get("document_id", "unknown")
        heading_path = doc.metadata.get("heading_path", "")
        # 逻辑 chunk_id = sha256(document_id + heading_path + text)
        logical_id = make_chunk_id(doc_id, heading_path, doc.page_content.strip())
        # Qdrant Point ID 必须是 UUID，从逻辑 ID 派生
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, logical_id))

        doc.metadata["chunk_id"] = logical_id
        doc.metadata["content_hash"] = _content_hash(doc.page_content)
        doc.metadata["indexed_at"] = now
        doc.metadata["collection_name"] = collection_name
        uuids.append(point_id)
        chunk_ids.append(logical_id)

    vector_store.add_documents(documents, ids=uuids, batch_size=batch_size)
    return chunk_ids


def _content_hash(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def search(
    collection_name: str,
    query: str,
    embeddings,
    top_k: int = 5,
) -> list[Document]:
    """在指定 collection 中搜索。"""
    from langchain_qdrant import QdrantVectorStore

    vector_store = QdrantVectorStore(
        client=get_client(),
        collection_name=collection_name,
        embedding=embeddings,
    )
    return vector_store.similarity_search(query, k=top_k)


def delete_by_document_id(collection_name: str, document_id: str) -> int:
    """按 document_id 删除旧 chunks。

    Qdrant 不返回精确删除数量，因此成功时返回 1 作为操作成功标记。
    删除失败必须向上抛出，调用方不得继续写入新的 Manifest 状态。
    """
    client = get_client()
    client.delete(
        collection_name=collection_name,
        points_selector=qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.document_id",
                    match=qdrant_models.MatchValue(value=document_id),
                )
            ]
        ),
        wait=True,
    )
    return 1


def get_collection_info(collection_name: str) -> dict:
    """获取 collection 统计信息。"""
    client = get_client()
    try:
        info = client.get_collection(collection_name)
        return {
            "name": collection_name,
            "points_count": info.points_count or 0,
        }
    except Exception:
        return {"name": collection_name, "vectors_count": 0, "points_count": 0, "error": "not found"}
