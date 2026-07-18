"""搜索接口。"""

from fastapi import APIRouter

from rag_app.models.requests import SearchRequest
from rag_app.models.responses import SearchResult
from rag_app.services.search_service import SearchService

router = APIRouter()
_search_service = None


def _get_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


@router.post("/search", response_model=SearchResult)
async def search(req: SearchRequest):
    svc = _get_service()
    result = svc.search(
        query=req.query,
        index_scope=req.index_scope.value,
        top_k=req.top_k,
        filters=req.filters,
    )
    return result
