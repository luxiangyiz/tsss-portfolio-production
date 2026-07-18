"""Markdown 解析器 — 解析 YAML frontmatter 和 Markdown 正文，提取标题路径。"""

import re
from pathlib import Path
from typing import Optional, Tuple

import yaml

from rag_app.knowledge.scanner import FileEntry
from rag_app.models.documents import Frontmatter, KBFile


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def extract_heading_path(text: str) -> str:
    """从 Markdown 正文中提取标题路径，如 '## 岗位职责 > ### 主要工作'。"""
    headings = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"^#{1,4}\s", stripped):
            headings.append(re.sub(r"^#+\s*", "", stripped))
    return " > ".join(headings)


class MarkdownParser:
    """解析 Markdown 文件，提取 frontmatter、正文和标题路径。"""

    def parse(self, entry: FileEntry) -> KBFile:
        raw = entry.absolute_path

        try:
            with open(raw, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return KBFile(
                relative_path=entry.relative_path,
                absolute_path=entry.absolute_path,
                file_name=entry.file_name,
                raw_content="",
                body_text="",
                size_bytes=entry.size_bytes,
                modified_at=entry.modified_at,
                parse_errors=[f"Failed to read file: {e}"],
            )

        fm, body, errors = self._split_frontmatter(content)
        frontmatter, fm_error = self._parse_frontmatter(fm)
        if fm_error:
            errors.append(fm_error)

        if frontmatter.privacy_level not in ("private", "internal", "public"):
            errors.append(f"Invalid privacy_level: {frontmatter.privacy_level}")

        # 提取标题路径
        heading_path = extract_heading_path(body)

        return KBFile(
            relative_path=entry.relative_path,
            absolute_path=entry.absolute_path,
            file_name=entry.file_name,
            frontmatter=frontmatter,
            raw_content=content,
            body_text=body,
            size_bytes=entry.size_bytes,
            modified_at=entry.modified_at,
            parse_errors=errors,
            heading_path=heading_path,
        )

    def _split_frontmatter(self, content: str) -> Tuple[str, str, list[str]]:
        errors: list[str] = []
        m = _FRONTMATTER_RE.match(content)
        if m:
            fm_text = m.group(1)
            body = content[m.end():]
            return fm_text, body, errors
        else:
            errors.append("No YAML frontmatter found; using defaults.")
            return "", content, errors

    def _parse_frontmatter(self, fm_text: str):
        if not fm_text.strip():
            return Frontmatter(), ""

        try:
            data = yaml.safe_load(fm_text)
        except yaml.YAMLError as e:
            return Frontmatter(), f"YAML parse error: {e}"

        if not isinstance(data, dict):
            return Frontmatter(), "YAML content is not a dict"

        return Frontmatter(
            doc_id=str(data.get("id", data.get("doc_id", ""))),
            title=str(data.get("title", "")),
            category=str(data.get("category", "")),
            tags=data.get("tags") if isinstance(data.get("tags"), list) else [],
            source=str(data.get("source", "")),
            source_type=str(data.get("source_type", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            verification_status=str(data.get("verification_status", "pending")),
            evidence=data.get("evidence") if isinstance(data.get("evidence"), list) else [],
            privacy_level=str(data.get("privacy_level", "")),
            publish_status=str(data.get("publish_status", "draft")),
            ai_generated=bool(data.get("ai_generated", False)),
            review_status=str(data.get("review_status", "pending")),
            related=data.get("related") if isinstance(data.get("related"), list) else [],
            notes=str(data.get("notes", "")),
        ), ""
