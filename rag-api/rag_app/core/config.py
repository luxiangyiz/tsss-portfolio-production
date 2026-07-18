"""核心配置模块 — 从 YAML 和 .env 加载所有配置。"""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


def _load_yaml_config(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_YAML = _load_yaml_config(Path(__file__).parent.parent.parent.parent / "configs" / "rag_config.yaml")


class Settings(BaseSettings):
    """RAG 系统配置，从 .env 和 YAML 合并。"""

    # ---------- 路径 ----------
    kb_root: str = _YAML.get("knowledge_base", {}).get("root", "")
    rag_data_dir: str = Field(default="data/rag", alias="RAG_DATA_DIR")
    log_dir: str = Field(default="logs", alias="LOG_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---------- Runtime ----------
    app_env: str = Field(default="development", alias="APP_ENV")
    rag_runtime_mode: str = Field(default="real_local", alias="RAG_RUNTIME_MODE")
    allow_fake_mode: bool = Field(default=False, alias="ALLOW_FAKE_MODE")
    demo_host: str = Field(default="127.0.0.1", alias="DEMO_HOST")
    demo_port: int = Field(default=8000, alias="DEMO_PORT")

    # ---------- Qdrant ----------
    qdrant_url: Optional[str] = Field(default=None, alias="QDRANT_URL")
    qdrant_path: str = Field(default="data/rag/qdrant", alias="QDRANT_PATH")

    # ---------- Embedding ----------
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_base_url: Optional[str] = Field(default=None, alias="EMBEDDING_BASE_URL")
    embedding_api_key: Optional[str] = Field(default=None, alias="EMBEDDING_API_KEY")

    # ---------- LLM ----------
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_base_url: Optional[str] = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: Optional[str] = Field(default=None, alias="LLM_API_KEY")

    # ---------- API ----------
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # ---------- RAG ----------
    default_index_scope: str = Field(default="internal", alias="DEFAULT_INDEX_SCOPE")
    rag_top_k: int = _YAML.get("rag", {}).get("top_k", 5)
    rag_chunk_size: int = _YAML.get("rag", {}).get("chunk_size", 500)
    rag_chunk_overlap: int = _YAML.get("rag", {}).get("chunk_overlap", 75)
    include_disputed: bool = _YAML.get("rag", {}).get("include_disputed", False)
    embedding_dimension: int = _YAML.get("rag", {}).get("embedding_dimension", 1536)
    relevance_threshold: float = _YAML.get("rag", {}).get("relevance_threshold", 0.3)

    # ---------- YAML 配置（直接透传） ----------
    yaml_config: dict = _YAML

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()


def validate_runtime_security() -> None:
    """校验本地演示运行模式和监听边界。"""
    valid_modes = {"offline_demo", "real_local"}
    if settings.rag_runtime_mode not in valid_modes:
        raise ValueError(
            f"RAG_RUNTIME_MODE must be one of {sorted(valid_modes)}, "
            f"got {settings.rag_runtime_mode!r}"
        )

    if settings.rag_runtime_mode == "offline_demo":
        local_hosts = {"127.0.0.1", "localhost", "::1"}
        if not settings.allow_fake_mode:
            raise ValueError("offline_demo requires ALLOW_FAKE_MODE=true")
        if settings.demo_host not in local_hosts or settings.api_host not in local_hosts:
            raise ValueError("offline_demo may only bind to 127.0.0.1 or localhost")
        if settings.cors_origins.strip():
            raise ValueError("offline_demo requires CORS_ORIGINS to be empty")


def get_effective_relevance_threshold() -> float:
    """Offline Demo展示Fake召回；真实模式继续使用生产阈值。"""
    if settings.rag_runtime_mode == "offline_demo":
        return 0.0
    return settings.relevance_threshold


def get_default_embedding_kwargs() -> dict:
    kwargs: dict = {
        "model": settings.embedding_model,
        "dimensions": settings.embedding_dimension,
        "check_embedding_ctx_length": False,
    }
    if settings.embedding_api_key:
        kwargs["api_key"] = settings.embedding_api_key
    if settings.embedding_base_url:
        kwargs["base_url"] = settings.embedding_base_url
    return kwargs


def get_default_llm_kwargs() -> dict:
    kwargs: dict = {"model": settings.llm_model, "temperature": 0.0}
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return kwargs
