"""API 请求模型。"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from rag_app.core.config import settings


class IndexScope(str, Enum):
    private = "private"
    internal = "internal"
    public = "public"


class IngestScope(str, Enum):
    private = "private"
    internal = "internal"
    public = "public"
    all = "all"


class IngestMode(str, Enum):
    full = "full"
    incremental = "incremental"


class IngestRequest(BaseModel):
    mode: IngestMode = IngestMode.incremental
    scope: IngestScope = IngestScope.all


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    index_scope: IndexScope = IndexScope.internal
    top_k: int = Field(default=5, ge=1, le=20)
    filters: dict = Field(default_factory=dict)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    index_scope: IndexScope = IndexScope.internal
    top_k: int = Field(default=5, ge=1, le=20)
    filters: dict = Field(default_factory=dict)


class PublicAskRequest(BaseModel):
    """Public website request. Scope, filters and top_k are server-controlled."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=settings.rag_max_input_length)


class PublicSearchRequest(BaseModel):
    """Public website search request with a deliberately minimal surface."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=settings.rag_max_input_length)
