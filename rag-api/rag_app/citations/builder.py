"""引用构建器 — 从检索结果构建 Citation。"""

from rag_app.models.responses import Citation


def build_citations(documents: list) -> list[Citation]:
    """从检索到的 LangChain Document 列表构建 Citation 列表。

    每条引用包含：document_id、标题、相对路径、heading path、命中文本片段、verification status。
    """
    citations = []
    for doc in documents:
        md = doc.metadata
        citations.append(Citation(
            document_id=md.get("document_id", ""),
            source_file=md.get("relative_path", md.get("file_path", "")),
            title=md.get("document_title", md.get("title", "")),
            heading_path=md.get("heading_path", ""),
            snippet=doc.page_content[:200],
            privacy_level=md.get("privacy_level", ""),
            verification_status=md.get("verification_status", ""),
        ))
    return citations
