"""OFFLINE DEMO专用的确定性模型实现，不依赖tests包。"""

import hashlib
from typing import List

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class DemoEmbeddings(Embeddings):
    """确定性1-gram + 2-gram哈希向量，仅用于工程演示。"""

    def __init__(self, dimension: int = 1536):
        super().__init__()
        self._dimension = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self._dimension
        for character in text:
            digest = hashlib.sha256(character.encode("utf-8")).hexdigest()
            vector[int(digest[:8], 16) % self._dimension] += 1.0
        for index in range(len(text) - 1):
            bigram = text[index:index + 2]
            digest = hashlib.sha256(bigram.encode("utf-8")).hexdigest()
            vector[int(digest[:8], 16) % self._dimension] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


class DemoChatModel(BaseChatModel):
    """根据已检索上下文返回确定性演示回答。"""

    def _generate(self, messages: List[BaseMessage], stop=None, **kwargs) -> ChatResult:
        document_count = 0
        for message in messages:
            content = str(getattr(message, "content", ""))
            document_count += content.count("[文档")
        if document_count:
            answer = (
                f"离线演示模型已依据 {document_count} 段知识库证据生成结果。"
                "请查看下方引用核对原始资料。"
            )
        else:
            answer = "知识库中暂无足够依据。"
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=answer))]
        )

    @property
    def _llm_type(self) -> str:
        return "demo-fake-chat"


def create_demo_embeddings(dimension: int = 1536) -> DemoEmbeddings:
    return DemoEmbeddings(dimension=dimension)


def create_demo_chat_model() -> DemoChatModel:
    return DemoChatModel()
