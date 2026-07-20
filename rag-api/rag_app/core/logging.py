"""日志模块 — 结构化日志 + 敏感字段脱敏。"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rag_app.core.config import settings
from rag_app.core.security import sanitize_dict, check_no_secrets_in_text


def setup_logging():
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / "rag_app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            file_handler,
        ],
    )


def sanitized_info(logger: logging.Logger, msg: str, extra: dict = None):
    """记录 INFO 日志，自动脱敏。"""
    if extra:
        safe_extra = sanitize_dict(extra)
        logger.info(msg, extra=safe_extra)
    else:
        logger.info(msg)


def log_search(logger: logging.Logger, trace_id: str, index_scope: str, query: str, 
               hit_count: int, latency_ms: float):
    """记录检索操作。"""
    logger.info(
        f"search trace={trace_id} scope={index_scope} hits={hit_count} latency={latency_ms:.0f}ms"
    )


def log_ask(logger: logging.Logger, trace_id: str, index_scope: str, status: str, 
            citation_count: int, latency_ms: float):
    """记录问答操作。"""
    logger.info(
        f"ask trace={trace_id} scope={index_scope} status={status} citations={citation_count} latency={latency_ms:.0f}ms"
    )
