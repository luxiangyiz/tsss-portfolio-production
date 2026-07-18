"""确定性 Fake Embeddings — 改进的 n-gram 哈希，提高 recall。"""

import hashlib
from typing import List
from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    """确定性假向量，使用 1-gram + 2-gram 混合哈希，提升中文检索 recall。"""

    def __init__(self, dimension: int = 128):
        super().__init__()
        self._dim = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self._dim

        # 1-gram（每个字符独立映射到固定桶）
        for c in text:
            h = hashlib.sha256(c.encode("utf-8")).hexdigest()
            idx = int(h[:8], 16) % self._dim
            vec[idx] += 1.0

        # 2-gram（字符对映射）
        for i in range(len(text) - 1):
            bigram = text[i:i+2]
            h = hashlib.sha256(bigram.encode("utf-8")).hexdigest()
            idx = int(h[:8], 16) % self._dim
            vec[idx] += 1.0

        # normalize
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]
