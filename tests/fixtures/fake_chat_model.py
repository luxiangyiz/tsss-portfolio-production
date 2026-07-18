"""Fake Chat Model — 简单回显，拒答由 answer_service 处理。"""

from typing import List
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration


class FakeChatModel(BaseChatModel):
    """永远基于 context 回答。真实拒答由 answer_service 的 relevance_threshold 和 refusal 检测处理。"""

    def _generate(self, messages: List[BaseMessage], stop=None, **kwargs) -> ChatResult:
        docs_count = 0
        for msg in messages:
            if hasattr(msg, "content"):
                c = str(msg.content)
                docs_count += c.count("[文档")
        answer = f"Based on {docs_count} document(s), here is the answer." if docs_count > 0 else "无法回答。"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=answer))])

    @property
    def _llm_type(self) -> str:
        return "fake-chat"
