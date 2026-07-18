"""Chunk ID 生成 — 稳定、可追溯的 chunk 标识。

格式：sha256(document_id + heading_path + normalized_chunk_text)
"""

import hashlib


def make_chunk_id(document_id: str, heading_path: str, normalized_text: str) -> str:
    """基于 document_id + heading_path + 内容生成唯一 ID。"""
    raw = f"{document_id}|{heading_path}|{normalized_text}"
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{document_id}#{content_hash}"
