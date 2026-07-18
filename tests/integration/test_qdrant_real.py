"""集成测试 — Fake Embedding + 真实本地 Qdrant。每个测试独立 collection。"""

import sys, os, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from langchain_core.documents import Document
from rag_app.langchain_components.vector_store import (
    ensure_collection, delete_collection, add_documents, search, delete_by_document_id,
)
from rag_app.knowledge.chunk_id import make_chunk_id
from tests.fixtures.fake_embeddings import FakeEmbeddings

FAKE_DIM = 128

@pytest.fixture
def emb():
    return FakeEmbeddings(dimension=FAKE_DIM)

@pytest.fixture
def col(monkeypatch):
    monkeypatch.setattr("rag_app.core.config.settings.embedding_dimension", FAKE_DIM)
    name = f"test_{uuid.uuid4().hex[:8]}"
    yield name
    delete_collection(name)

class TestQdrantWriteSearch:
    def test_write_and_search(self, emb, col):
        doc = Document(page_content="钟伟达在厦门特房建工实习，参与主体结构施工管理。", metadata={
            "document_id":"kb-02-002","document_title":"实习经历","relative_path":"02/test.md",
            "privacy_level":"internal","verification_status":"pending","heading_path":"## 主要工作"})
        add_documents(col, [doc], emb)
        results = search(col, "施工管理", emb, top_k=3)
        assert len(results) > 0

    def test_document_deletion(self, emb, col):
        doc_id = "test-del-001"
        doc = Document(page_content="会被删除的内容。", metadata={"document_id":doc_id,"document_title":"T",
            "relative_path":"t.md","privacy_level":"internal","verification_status":"pending"})
        add_documents(col, [doc], emb)
        delete_by_document_id(col, doc_id)
        results = search(col, "删除", emb, top_k=5)
        assert doc_id not in [r.metadata.get("document_id") for r in results]

    def test_chunk_id_in_metadata(self, emb, col):
        doc = Document(page_content="测试chunk_id存储ABC。", metadata={"document_id":"kb-test-id",
            "document_title":"T","relative_path":"t.md","privacy_level":"internal","verification_status":"pending"})
        add_documents(col, [doc], emb)
        results = search(col, "ABC", emb, top_k=1)
        assert len(results) > 0
        assert results[0].metadata["chunk_id"].startswith("kb-test-id#")

    def test_incremental_update(self, emb, col):
        doc_id = "incr-001"
        doc_old = Document(page_content="旧版本内容苹果。", metadata={"document_id":doc_id,"document_title":"T",
            "relative_path":"t.md","privacy_level":"internal","verification_status":"pending"})
        doc_new = Document(page_content="新版本内容香蕉。", metadata={"document_id":doc_id,"document_title":"T",
            "relative_path":"t.md","privacy_level":"internal","verification_status":"pending"})
        add_documents(col, [doc_old], emb)
        delete_by_document_id(col, doc_id)
        add_documents(col, [doc_new], emb)
        results = search(col, "香蕉", emb, top_k=3)
        assert len(results) > 0
        assert "香蕉" in results[0].page_content

    def test_delete_failure_propagates(self, monkeypatch):
        class FailingClient:
            def delete(self, **kwargs):
                raise RuntimeError("simulated qdrant delete failure")

        monkeypatch.setattr(
            "rag_app.langchain_components.vector_store.get_client",
            lambda: FailingClient(),
        )
        with pytest.raises(RuntimeError, match="delete failure"):
            delete_by_document_id("test_collection", "doc-1")

class TestPrivacyWithFake:
    def test_private_not_in_public(self, emb, monkeypatch):
        monkeypatch.setattr("rag_app.core.config.settings.embedding_dimension", FAKE_DIM)
        priv_col = f"test_pvt_{uuid.uuid4().hex[:8]}"
        pub_col = f"test_pub_{uuid.uuid4().hex[:8]}"
        try:
            ensure_collection(pub_col)
            doc = Document(page_content="私人机密数据XYZ。", metadata={"document_id":"kb-priv",
                "document_title":"P","relative_path":"01/p.md","privacy_level":"private","verification_status":"pending"})
            add_documents(priv_col, [doc], emb)
            results = search(pub_col, "XYZ", emb, top_k=5)
            found = [r for r in results if "XYZ" in r.page_content]
            assert len(found) == 0
        finally:
            delete_collection(priv_col)
            delete_collection(pub_col)

class TestChunkIdStability:
    def test_same_same(self):
        assert make_chunk_id("kb-001", "## T", "X") == make_chunk_id("kb-001", "## T", "X")
    def test_diff_diff(self):
        assert make_chunk_id("kb-001", "## T", "A") != make_chunk_id("kb-001", "## T", "B")
