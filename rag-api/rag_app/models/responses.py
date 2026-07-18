"""API 响应模型 — 对齐任务单字段。"""

from typing import Optional

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: str = "ok"
    qdrant: str = "ok"
    embedding: str = "ok"
    llm: str = "ok"
    collections: dict = Field(default_factory=dict)
    runtime_mode: str = "real_local"
    runtime_label: str = "REAL LOCAL"
    embedding_model: str = ""
    llm_model: str = ""
    local_only: bool = True
    limitations: list[str] = Field(default_factory=list)


class IndexStats(BaseModel):
    collection_name: str
    document_count: int
    chunk_count: int
    last_build: Optional[str] = None
    error_count: int = 0


class IndexStatsResponse(BaseModel):
    collections: list[IndexStats] = Field(default_factory=list)


class IngestResult(BaseModel):
    mode: str
    scope: str
    scanned_files: int
    included_files: int
    excluded_files: int
    rejected_files: int
    total_chunks: int
    chunks_by_collection: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    added_files: int = 0
    updated_files: int = 0
    metadata_changed_files: int = 0
    deleted_files: int = 0
    skipped_files: int = 0
    written_chunks: int = 0
    deleted_chunks: int = 0


class SearchHit(BaseModel):
    chunk_id: str
    score: float
    content: str
    metadata: dict = Field(default_factory=dict)


class SearchResult(BaseModel):
    query: str
    index_scope: str
    hits: list[SearchHit] = Field(default_factory=list)
    retrieved_count: int = 0
    latency_ms: float = 0.0
    trace_id: str = ""


class Citation(BaseModel):
    document_id: str = ""
    source_file: str = ""
    title: str = ""
    heading_path: str = ""
    snippet: str = ""
    privacy_level: str = ""
    verification_status: str = ""


class AskResult(BaseModel):
    status: str = "answered"  # answered / insufficient_context / privacy_blocked / configuration_error
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    index_scope: str = ""
    retrieved_count: int = 0
    latency_ms: float = 0.0
    trace_id: str = ""
    disclaimer: str = ""


class PublicCitation(BaseModel):
    title: str = ""
    heading_path: str = ""
    snippet: str = ""


class PublicAskResult(BaseModel):
    status: str = "answered"
    answer: str = ""
    citations: list[PublicCitation] = Field(default_factory=list)
    retrieved_count: int = 0
    latency_ms: float = 0.0
    request_id: str = ""
    disclaimer: str = ""


class PublicSearchHit(BaseModel):
    score: float
    content: str
    title: str = ""
    heading_path: str = ""


class PublicSearchResult(BaseModel):
    hits: list[PublicSearchHit] = Field(default_factory=list)
    retrieved_count: int = 0
    latency_ms: float = 0.0
    request_id: str = ""
