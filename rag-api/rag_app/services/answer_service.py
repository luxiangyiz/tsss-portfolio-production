"""问答服务 — 基于检索结果的 RAG 问答。"""

import logging
import time
import uuid

from rag_app.core.config import get_effective_relevance_threshold
from rag_app.core.exceptions import InvalidScopeError
from rag_app.langchain_components.chat_model import create_chat_model
from rag_app.langchain_components.prompts import RAG_QA_PROMPT
from rag_app.citations.builder import build_citations
from rag_app.models.responses import AskResult
from rag_app.services.search_service import SearchService
from rag_app.services.evidence_policy import EvidenceSufficiencyPolicy

logger = logging.getLogger(__name__)


class AnswerService:
    """RAG 问答服务。"""

    def __init__(self):
        self.search_service = SearchService()
        self._llm = None
        self._relevance_threshold = get_effective_relevance_threshold()
        self._evidence = EvidenceSufficiencyPolicy()

    @property
    def llm(self):
        if self._llm is None:
            self._llm = create_chat_model()
        return self._llm

    def ask(self, question: str, index_scope: str, top_k: int = 5, filters: dict = None) -> AskResult:
        start = time.time()
        trace_id = str(uuid.uuid4())[:8]

        if index_scope not in ("private", "internal", "public"):
            raise InvalidScopeError(f"Invalid index_scope: {index_scope}")

        # Step 1: 检索
        try:
            search_result = self.search_service.search(question, index_scope, top_k, filters)
        except Exception as e:
            # SearchService 异常不吞掉，记录日志但对外不暴露堆栈
            logger.error(f"Search failed trace={trace_id} scope={index_scope} error={type(e).__name__}")
            latency = (time.time() - start) * 1000
            return AskResult(
                status="configuration_error",
                answer="",
                citations=[],
                index_scope=index_scope,
                retrieved_count=0,
                latency_ms=round(latency, 1),
                trace_id=trace_id,
                disclaimer="检索服务暂时不可用，请稍后重试。",
            )

        # Step 1.5: 证据充分性判断 — 不只是"有hit就回答"
        if not search_result.hits:
            latency = (time.time() - start) * 1000
            return AskResult(
                status="insufficient_context",
                answer="知识库中暂无足够依据。",
                citations=[],
                index_scope=index_scope,
                retrieved_count=0,
                latency_ms=round(latency, 1),
                trace_id=trace_id,
                disclaimer="此回答仅基于知识库索引内容。",
            )

        # 当最高相关度分数 < relevance_threshold 时返回 insufficient_context
        top_score = search_result.hits[0].score if search_result.hits else 0
        if top_score < self._relevance_threshold:
            latency = (time.time() - start) * 1000
            return AskResult(
                status="insufficient_context",
                answer="根据现有资料，我无法回答这个问题。",
                citations=[],
                index_scope=index_scope,
                retrieved_count=len(search_result.hits),
                latency_ms=round(latency, 1),
                trace_id=trace_id,
                disclaimer="此回答仅基于知识库索引内容。检索到部分结果但相关度不足。",
            )

        # 证据充分性检查
        mock_hits = [type("H", (), {"page_content": h.content, "metadata": h.metadata, "score": h.score})() for h in search_result.hits]
        sufficient, reason = self._evidence.is_sufficient(question, mock_hits, index_scope)
        if not sufficient:
            latency = (time.time() - start) * 1000
            return AskResult(
                status="insufficient_context",
                answer="知识库中暂无足够依据。",
                citations=[],
                index_scope=index_scope,
                retrieved_count=0,
                latency_ms=round(latency, 1),
                trace_id=trace_id,
                disclaimer=f"证据不足({reason})。",
            )

        # Step 2: 构建上下文
        context_parts: list[str] = []
        for i, hit in enumerate(search_result.hits, 1):
            md = hit.metadata
            title = md.get("document_title", "Untitled")
            context_parts.append(f"[文档{i}] {title}\n{hit.content}")

        context = "\n\n---\n\n".join(context_parts)
        citations = build_citations(
            [type("D", (), {"metadata": h.metadata, "page_content": h.content})() for h in search_result.hits]
        )

        # Step 3: LLM 生成
        try:
            messages = RAG_QA_PROMPT.format_messages(context=context, question=question)
            response = self.llm.invoke(messages)
            answer = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            # 区分 configuration_error（无LLM）和其他异常
            logger.error("llm_failed trace=%s scope=%s error_type=%s", trace_id, index_scope, type(e).__name__)
            latency = (time.time() - start) * 1000
            return AskResult(
                status="configuration_error",
                answer="",
                citations=citations,
                index_scope=index_scope,
                retrieved_count=len(citations),
                latency_ms=round(latency, 1),
                trace_id=trace_id,
                disclaimer="语言模型暂时不可用。检索已完成，但无法生成回答。请检查 LLM 配置。",
            )

        # 检测 LLM 拒答
        refusal_keywords = ["无法回答", "资料不足", "暂无足够", "我不确定", "没有相关"]
        if any(kw in answer for kw in refusal_keywords):
            latency = (time.time() - start) * 1000
            return AskResult(
                status="insufficient_context",
                answer=answer,
                citations=citations,
                index_scope=index_scope,
                retrieved_count=len(citations),
                latency_ms=round(latency, 1),
                trace_id=trace_id,
                disclaimer="此回答仅基于知识库索引内容。",
            )

        # 检查是否有待核实内容
        has_pending = any(
            c.verification_status == "pending" for c in citations
        )
        disclaimer = ""
        if has_pending:
            disclaimer = "⚠️ 部分引用内容尚未核实（verification_status: pending），请以原始资料为准。"

        latency = (time.time() - start) * 1000
        return AskResult(
            status="answered",
            answer=answer,
            citations=citations,
            index_scope=index_scope,
            retrieved_count=len(citations),
            latency_ms=round(latency, 1),
            trace_id=trace_id,
            disclaimer=disclaimer,
        )
