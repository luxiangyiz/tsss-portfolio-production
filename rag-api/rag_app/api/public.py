"""Public website API with a server-enforced public knowledge boundary."""

import re

from fastapi import APIRouter

from rag_app.models.requests import PublicAskRequest, PublicSearchRequest
from rag_app.models.responses import (
    PublicAskResult,
    PublicCitation,
    PublicSearchHit,
    PublicSearchResult,
)
from rag_app.services.answer_service import AnswerService
from rag_app.services.search_service import SearchService

router = APIRouter(prefix="/public", tags=["public"])

PUBLIC_TOP_K = 5
PUBLIC_FILTERS = {
    "privacy_level": "public",
    "publish_status": "published",
    "review_status": "approved",
    "verification_status": "verified",
}

_answer_service = None
_search_service = None


def _clean_public_answer(answer: str) -> str:
    cleaned = re.sub(r"\s*[\[【]来源\s*[:：][^\]】]*[\]】]", "", answer)
    return cleaned.strip()


def _get_answer_service() -> AnswerService:
    global _answer_service
    if _answer_service is None:
        _answer_service = AnswerService()
    return _answer_service


def _get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


@router.get("/health")
async def public_health():
    return {"status": "ok"}


@router.post("/ask", response_model=PublicAskResult)
async def public_ask(req: PublicAskRequest):
    result = _get_answer_service().ask(
        question=req.question,
        index_scope="public",
        top_k=PUBLIC_TOP_K,
        filters=PUBLIC_FILTERS,
    )
    citations = [
        PublicCitation(
            title=citation.title,
            heading_path=citation.heading_path,
            snippet=citation.snippet,
        )
        for citation in result.citations
        if citation.privacy_level == "public"
        and citation.verification_status == "verified"
    ]
    return PublicAskResult(
        status=result.status,
        answer=_clean_public_answer(result.answer),
        citations=citations,
        retrieved_count=len(citations),
        latency_ms=result.latency_ms,
        request_id=result.trace_id,
        disclaimer=result.disclaimer,
    )


@router.post("/search", response_model=PublicSearchResult)
async def public_search(req: PublicSearchRequest):
    result = _get_search_service().search(
        query=req.query,
        index_scope="public",
        top_k=PUBLIC_TOP_K,
        filters=PUBLIC_FILTERS,
    )
    hits = [
        PublicSearchHit(
            score=hit.score,
            content=hit.content,
            title=hit.metadata.get("document_title", ""),
            heading_path=hit.metadata.get("heading_path", ""),
        )
        for hit in result.hits
        if hit.metadata.get("privacy_level") == "public"
        and hit.metadata.get("verification_status") == "verified"
        and hit.metadata.get("publish_status") == "published"
        and hit.metadata.get("review_status") == "approved"
    ]
    return PublicSearchResult(
        hits=hits,
        retrieved_count=len(hits),
        latency_ms=result.latency_ms,
        request_id=result.trace_id,
    )
