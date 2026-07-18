"""纳入策略 — 决定文件是否进入索引。"""

from rag_app.core.config import settings
from rag_app.models.documents import KBFile


class InclusionPolicy:
    """根据 frontmatter 决定文件是否纳入索引。"""

    def __init__(self):
        self._include_disputed = settings.include_disputed

    def should_include(self, kb_file: KBFile) -> tuple[bool, str]:
        """返回 (是否纳入, 拒绝原因)。纳入返回 (True, "")。"""
        fm = kb_file.frontmatter

        # YAML 解析错误
        if kb_file.parse_errors:
            for err in kb_file.parse_errors:
                if "No YAML frontmatter" in err or "YAML" in err.lower():
                    pass  # 仅缺失 frontmatter 不拒绝，用默认值
                else:
                    return False, f"parse error: {kb_file.parse_errors[0]}"

        # 缺少 id
        if not fm.doc_id:
            return False, "missing id"

        # 缺少 privacy_level
        if not fm.privacy_level:
            return False, "missing privacy_level"

        # privacy_level 必须是合法值
        if fm.privacy_level not in ("private", "internal", "public"):
            return False, f"invalid privacy_level: {fm.privacy_level}"

        # disputed 内容开关
        if not self._include_disputed and fm.verification_status == "disputed":
            return False, "disputed content excluded by config"

        return True, ""
