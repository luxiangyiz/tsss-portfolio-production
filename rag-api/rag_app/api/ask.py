"""问答接口。"""

from fastapi import APIRouter

from rag_app.models.requests import AskRequest
from rag_app.models.responses import AskResult
from rag_app.services.answer_service import AnswerService

router = APIRouter()
_answer_service = None


def _get_service() -> AnswerService:
    global _answer_service
    if _answer_service is None:
        _answer_service = AnswerService()
    return _answer_service


@router.post("/ask", response_model=AskResult)
async def ask(req: AskRequest):
    svc = _get_service()
    result = svc.ask(
        question=req.question,
        index_scope=req.index_scope.value,
        top_k=req.top_k,
        filters=req.filters,
    )
    return result
