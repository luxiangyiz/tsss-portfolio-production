"""文本切分器 — 按 Markdown 标题语义切分，保留 heading path。"""

import re
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_app.core.config import settings


def _extract_headings(text: str) -> str:
    """提取文本中的所有标题路径，如 '## 岗位职责 > ### 主要工作'。"""
    headings = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"^#{1,4}\s", stripped):
            headings.append(re.sub(r"^#+\s*", "", stripped))
    return " > ".join(headings)


def create_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        separators=["\n## ", "\n### ", "\n#### ", "\n", "。", ".", " ", ""],
        keep_separator=True,
    )


def split_document_with_headings(doc: Document) -> List[Document]:
    """先按 ## 标题切分章节，再对过长的章节使用 RecursiveCharacterTextSplitter。

    每个 chunk 的 metadata 中注入 heading_path。
    """
    splitter = create_splitter()
    content = doc.page_content
    metadata = doc.metadata

    # Step 1: 按 H2 标题拆分
    sections = re.split(r"\n(?=## )", content)
    chunks: List[Document] = []

    for section in sections:
        if not section.strip():
            continue
        heading_path = _extract_headings(section)
        # Step 2: 对过长 section 使用 LangChain splitter
        if len(section) > settings.rag_chunk_size * 2:
            sub_docs = [Document(page_content=s, metadata={**metadata}) for s in [section]]
            sub_chunks = splitter.split_documents(sub_docs)
            for ch in sub_chunks:
                ch.metadata["heading_path"] = heading_path
                chunks.append(ch)
        else:
            new_meta = {**metadata, "heading_path": heading_path}
            chunks.append(Document(page_content=section.strip(), metadata=new_meta))

    return chunks
