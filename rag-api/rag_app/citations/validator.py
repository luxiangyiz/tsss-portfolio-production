"""引用验证器 — 检查检索结果与原始文件的一致性。"""


def validate_citation_snippet(citation, kb_root: str) -> bool:
    """验证 citation 的 snippet 是否能在源文件中找到。"""
    import os
    file_path = os.path.join(kb_root, citation.source_file)
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 简单子串匹配（忽略空白差异）
        snippet_clean = "".join(citation.snippet.split())
        content_clean = "".join(content.split())
        return snippet_clean[:50] in content_clean
    except Exception:
        return False
