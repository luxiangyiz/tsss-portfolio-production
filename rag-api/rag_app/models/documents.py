"""Pydantic 文档模型 — 知识库解析后的内部文档结构。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Frontmatter(BaseModel):
    """Markdown YAML frontmatter 解析结果。"""
    doc_id: str = ""
    title: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    source_type: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    verification_status: str = "pending"
    evidence: list[str] = Field(default_factory=list)
    privacy_level: str = "internal"
    publish_status: str = "draft"
    ai_generated: bool = False
    review_status: str = "pending"
    related: list[str] = Field(default_factory=list)
    notes: str = ""

    # 允许额外字段（用户自定义）
    model_config = {"extra": "allow"}


class KBFile(BaseModel):
    """知识库中的单个文件。"""
    relative_path: str              # 相对于 KB_ROOT 的路径
    absolute_path: str             # 完整路径
    file_name: str
    frontmatter: Frontmatter = Field(default_factory=Frontmatter)
    raw_content: str = ""          # 原始 Markdown 内容
    body_text: str = ""            # 去掉 frontmatter 后的正文
    size_bytes: int = 0
    modified_at: str = ""
    parse_errors: list[str] = Field(default_factory=list)
    heading_path: str = ""          # Markdown 标题路径
    inclusion_status: str = "candidate"  # candidate / included / excluded
    exclusion_reason: str = ""


class KBDocument(BaseModel):
    """经过 LangChain 处理前的文档对象。"""
    file: KBFile
    page_content: str              # 要索引的文本
    metadata: dict = Field(default_factory=dict)


class ChunkMetadata(BaseModel):
    """Chunk 元数据（存入 Qdrant payload）。"""
    doc_id: str
    title: str
    file_path: str
    privacy_level: str
    verification_status: str
    publish_status: str = "draft"
    review_status: str = "pending"
    ai_generated: bool = False
    chunk_index: int = 0
    total_chunks: int = 1
    heading_path: str = ""         # 标题路径，如 "## 岗位职责 > ### 主要工作"
    source_file: str = ""          # 源文件相对路径
    tags: list[str] = Field(default_factory=list)
    collection_name: str = ""      # 实际写入的 collection


class IngestPreview(BaseModel):
    """索引预览结果。"""
    scanned_files: int = 0
    included_files: int = 0
    excluded_files: int = 0
    rejected_files: int = 0
    files: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    stats_by_privacy: dict[str, int] = Field(default_factory=dict)
