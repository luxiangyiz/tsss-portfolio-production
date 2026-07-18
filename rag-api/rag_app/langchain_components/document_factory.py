"""Document Factory — 将 KBFile 转换为 LangChain Document，metadata 对齐任务单字段。"""

from langchain_core.documents import Document

from rag_app.models.documents import KBFile


def kb_file_to_langchain_document(kb_file: KBFile) -> Document:
    """将知识库文件转为 LangChain Document。metadata 对齐任务单字段名。"""
    fm = kb_file.frontmatter
    metadata = {
        "document_id": fm.doc_id,
        "document_title": fm.title,
        "relative_path": kb_file.relative_path,
        "category": fm.category,
        "tags": fm.tags,
        "source": fm.source,
        "privacy_level": fm.privacy_level,
        "verification_status": fm.verification_status,
        "publish_status": fm.publish_status,
        "review_status": fm.review_status,
        "ai_generated": fm.ai_generated,
        "updated_at": fm.updated_at,
    }
    return Document(page_content=kb_file.body_text, metadata=metadata)
