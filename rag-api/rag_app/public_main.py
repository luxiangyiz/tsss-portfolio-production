"""Public-only FastAPI entry point for the personal website deployment."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_app.api import public
from rag_app.core.config import settings, validate_runtime_security
from rag_app.core.logging import setup_logging

validate_runtime_security()
setup_logging()

app = FastAPI(
    title="钟伟达个人网站公开知识助手",
    description="Public-only RAG API. Private, internal and ingestion routes are not mounted.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

app.include_router(public.router)
