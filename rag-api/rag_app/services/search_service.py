"""搜索服务 — 按 scope 选择 collection 执行检索，支持相关度阈值和 filters。"""

import logging
import time
import uuid

from rag_app.core.config import get_effective_relevance_threshold
from rag_app.core.exceptions import InvalidScopeError
from rag_app.knowledge.privacy_router import PrivacyRouter
from rag_app.langchain_components.embeddings import create_embeddings
from rag_app.langchain_components.retriever import retrieve_with_scores
from rag_app.models.responses import SearchHit, SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """检索服务。"""

    def __init__(self):
        self.router = PrivacyRouter()
        self._embeddings = None
        self._threshold = get_effective_relevance_threshold()

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = create_embeddings()
        return self._embeddings

    def search(self, query: str, index_scope: str, top_k: int = 5, filters: dict = None) -> SearchResult:
        start = time.time()
        trace_id = str(uuid.uuid4())[:8]

        if index_scope not in ("private", "internal", "public"):
            raise InvalidScopeError(f"Invalid index_scope: {index_scope}")

        collections = self.router.get_target_collections(index_scope)
        if not collections:
            raise InvalidScopeError(f"No collections for scope: {index_scope}")

        all_hits: list[tuple] = []
        for col in collections:
            try:
                hits = retrieve_with_scores(col, query, self.embeddings, top_k * 2)
                all_hits.extend((doc, score) for doc, score in hits)
            except Exception as e:
                logger.warning(f"Retrieval failed for collection {col}: {e}")
                continue

        # 按分数排序、去重
        all_hits.sort(key=lambda x: x[1], reverse=True)
        seen = set()
        unique_hits = []
        for doc, score in all_hits:
            cid = doc.metadata.get("chunk_id", doc.page_content[:50])
            if cid not in seen:
                seen.add(cid)
                unique_hits.append((doc, score))

        # 应用相关度阈值
        if self._threshold > 0:
            unique_hits = [(d, s) for d, s in unique_hits if s >= self._threshold]

        # 应用 filters（category, tags, document_id, verification_status）
        if filters:
            unique_hits = self._apply_filters(unique_hits, filters)

        hits = []
        for doc, score in unique_hits[:top_k]:
            hits.append(SearchHit(
                chunk_id=doc.metadata.get("chunk_id", ""),
                score=round(score, 4),
                content=doc.page_content,
                metadata={
                    "document_id": doc.metadata.get("document_id", ""),
                    "document_title": doc.metadata.get("document_title", ""),
                    "relative_path": doc.metadata.get("relative_path", ""),
                    "heading_path": doc.metadata.get("heading_path", ""),
                    "category": doc.metadata.get("category", ""),
                    "tags": doc.metadata.get("tags", []),
                    "source": doc.metadata.get("source", ""),
                    "verification_status": doc.metadata.get("verification_status", ""),
                    "privacy_level": doc.metadata.get("privacy_level", ""),
                    "publish_status": doc.metadata.get("publish_status", ""),
                    "review_status": doc.metadata.get("review_status", ""),
                    "ai_generated": doc.metadata.get("ai_generated", False),
                    "updated_at": doc.metadata.get("updated_at", ""),
                    "content_hash": doc.metadata.get("content_hash", ""),
                    "indexed_at": doc.metadata.get("indexed_at", ""),
                },
            ))

        latency = (time.time() - start) * 1000
        return SearchResult(
            query=query,
            index_scope=index_scope,
            hits=hits,
            retrieved_count=len(hits),
            latency_ms=round(latency, 1),
            trace_id=trace_id,
        )

    def _apply_filters(self, hits: list[tuple], filters: dict) -> list[tuple]:
        """对检索结果应用元数据过滤。"""
        filtered = []
        for doc, score in hits:
            md = doc.metadata
            match = True

            if "category" in filters and filters["category"]:
                if md.get("category") != filters["category"]:
                    match = False

            if "tags" in filters and filters["tags"]:
                doc_tags = set(md.get("tags", []))
                req_tags = set(filters["tags"])
                if not req_tags.issubset(doc_tags):
                    match = False

            if "document_id" in filters and filters["document_id"]:
                if md.get("document_id") != filters["document_id"]:
                    match = False

            if "verification_status" in filters and filters["verification_status"]:
                if md.get("verification_status") != filters["verification_status"]:
                    match = False

            for field in ("privacy_level", "publish_status", "review_status"):
                if field in filters and filters[field]:
                    if md.get(field) != filters[field]:
                        match = False

            if match:
                filtered.append((doc, score))

        return filtered
