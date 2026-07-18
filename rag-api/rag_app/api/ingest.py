"""索引接口。"""

from fastapi import APIRouter

from rag_app.models.requests import IngestRequest
from rag_app.models.responses import IngestResult
from rag_app.services.ingestion_service import IngestionService

router = APIRouter()
_ingestion_service = None


def _get_service() -> IngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service


@router.post("/ingest/preview")
async def ingest_preview():
    svc = _get_service()
    preview = svc.preview()
    return preview  # dict, FastAPI 自动转 JSON


@router.post("/ingest", response_model=IngestResult)
async def ingest(req: IngestRequest):
    svc = _get_service()
    result = svc.ingest(mode=req.mode.value, scope=req.scope.value)
    return result
