"""证据充分性策略 — 通用规则判断检索结果是否支撑回答。"""

from rag_app.core.config import get_effective_relevance_threshold


class EvidenceSufficiencyPolicy:
    def __init__(self):
        self._threshold = get_effective_relevance_threshold()

    def is_sufficient(self, question: str, hits: list, index_scope: str = "internal") -> tuple[bool, str]:
        if not hits:
            return False, "no_hits"

        top_score = hits[0].score if hasattr(hits[0], 'score') else 0
        if self._threshold > 0 and top_score < self._threshold:
            return False, f"score_low({top_score:.3f})"

        content_text = " ".join(h.page_content if hasattr(h, 'page_content') else h.content for h in hits[:5])
        overlap = self._char_overlap(question, content_text)
        if overlap < 0.15:
            return False, f"low_overlap({overlap:.2f})"

        if self._is_personal_fact(question):
            personal_cats = {"个人档案", "教育经历", "工作经历", "项目案例", "技能证据"}
            personal_text = ""
            for h in hits[:5]:
                md = h.metadata if hasattr(h, 'metadata') else {}
                if md.get("category", "") in personal_cats:
                    personal_text += (h.page_content if hasattr(h, 'page_content') else h.content)
            if not personal_text:
                return False, "no_personal_evidence"
            if self._char_overlap(question, personal_text) < 0.1:
                return False, "personal_mismatch"

        return True, "sufficient"

    def _char_overlap(self, q: str, t: str) -> float:
        qc = set(c for c in q if '\u4e00' <= c <= '\u9fff')
        if not qc: return 1.0
        tc = set(c for c in t if '\u4e00' <= c <= '\u9fff')
        if not tc: return 0.0
        return len(qc & tc) / len(qc)

    def _is_personal_fact(self, q: str) -> bool:
        markers = ["我", "我的"]
        fact_words = ["是什么", "哪", "多少", "有没有", "是否", "什么", "哪些", "怎么"]
        return any(m in q for m in markers) and any(f in q for f in fact_words)
