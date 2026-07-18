"""FastAPI 集成测试 — Fake Embedding + Fake ChatModel 端到端。"""

import sys, os, uuid, tempfile, shutil
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.fake_embeddings import FakeEmbeddings
from tests.fixtures.fake_chat_model import FakeChatModel

FAKE_DIM = 128
KB_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ai-job-knowledge-base"))


def _fake_emb():
    return FakeEmbeddings(dimension=FAKE_DIM)

def _fake_chat():
    return FakeChatModel()


@pytest.fixture
def data_dir():
    d = tempfile.mkdtemp(prefix="rag_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def client(data_dir, monkeypatch):
    monkeypatch.setattr("rag_app.core.config.settings.kb_root", KB_ROOT)
    monkeypatch.setattr("rag_app.core.config.settings.rag_data_dir", data_dir)
    monkeypatch.setattr("rag_app.core.config.settings.qdrant_path", os.path.join(data_dir, "qdrant"))
    monkeypatch.setattr("rag_app.core.config.settings.embedding_dimension", FAKE_DIM)

    # 重置全局服务单例
    for mod in ["rag_app.services.ingestion_service", "rag_app.services.search_service",
                "rag_app.services.answer_service", "rag_app.api.ingest",
                "rag_app.api.search", "rag_app.api.ask", "rag_app.api.public"]:
        monkeypatch.setattr(f"{mod}._ingestion_service", None, raising=False)
        monkeypatch.setattr(f"{mod}._answer_service", None, raising=False)
        monkeypatch.setattr(f"{mod}._search_service", None, raising=False)

    from rag_app.main import app
    with (
        patch("rag_app.langchain_components.embeddings.create_embeddings", _fake_emb),
        patch("rag_app.services.ingestion_service.create_embeddings", _fake_emb),
        patch("rag_app.services.search_service.create_embeddings", _fake_emb),
        patch("rag_app.langchain_components.chat_model.create_chat_model", _fake_chat),
        patch("rag_app.services.answer_service.create_chat_model", _fake_chat),
        TestClient(app) as c,
    ):
        yield c


class TestHealth:
    def test_health(self, client):
        assert client.get("/health").status_code == 200

    def test_stats(self, client):
        assert client.get("/index/stats").status_code == 200


class TestIngest:
    def test_preview(self, client):
        r = client.post("/ingest/preview")
        assert r.status_code == 200
        assert r.json()["scanned_files"] > 0

    def test_full_build(self, client):
        r = client.post("/ingest", json={"mode": "full", "scope": "all"})
        assert r.status_code == 200
        assert r.json()["total_chunks"] > 0

    def test_incremental_after_full(self, client):
        client.post("/ingest", json={"mode": "full", "scope": "all"})
        r = client.post("/ingest", json={"mode": "incremental", "scope": "all"})
        assert r.status_code == 200
        assert "total_chunks" in r.json()


class TestSearch:
    def test_search_after_ingest(self, client):
        client.post("/ingest", json={"mode": "full", "scope": "all"})
        r = client.post("/search", json={"query": "test", "index_scope": "internal", "top_k": 3})
        assert r.status_code == 200

    def test_search_all_scope_rejected(self, client):
        r = client.post("/search", json={"query": "t", "index_scope": "all", "top_k": 3})
        assert r.status_code == 422


class TestAsk:
    def test_ask_after_ingest(self, client):
        client.post("/ingest", json={"mode": "full", "scope": "all"})
        r = client.post("/ask", json={"question": "test", "index_scope": "internal", "top_k": 3})
        assert r.status_code == 200
        assert r.json()["status"] in ("answered", "insufficient_context")

    def test_ask_empty_kb(self, client):
        r = client.post("/ask", json={"question": "X", "index_scope": "internal", "top_k": 3})
        assert r.status_code == 200
        assert "status" in r.json()


class TestPublicAPI:
    def test_public_endpoints_are_sanitized(self, client):
        client.post("/ingest", json={"mode": "full", "scope": "all"})

        ask_response = client.post(
            "/public/ask",
            json={"question": "钟伟达做过哪些项目？"},
        )
        assert ask_response.status_code == 200
        ask_payload = ask_response.json()
        assert "index_scope" not in ask_payload
        assert "trace_id" not in ask_payload
        for citation in ask_payload["citations"]:
            assert set(citation) == {"title", "heading_path", "snippet"}
            assert "source_file" not in citation
            assert "document_id" not in citation
            assert "privacy_level" not in citation

        search_response = client.post(
            "/public/search",
            json={"query": "钟伟达的AI项目"},
        )
        assert search_response.status_code == 200
        search_payload = search_response.json()
        for hit in search_payload["hits"]:
            assert set(hit) == {"score", "content", "title", "heading_path"}
            assert "metadata" not in hit
            assert "chunk_id" not in hit

    @pytest.mark.parametrize(
        "path,payload",
        [
            ("/public/ask", {"question": "test", "index_scope": "private"}),
            ("/public/ask", {"question": "test", "top_k": 20}),
            ("/public/search", {"query": "test", "index_scope": "internal"}),
            ("/public/search", {"query": "test", "filters": {}}),
        ],
    )
    def test_public_clients_cannot_override_server_controls(self, client, path, payload):
        response = client.post(path, json=payload)
        assert response.status_code == 422

    def test_public_question_length_is_limited(self, client):
        response = client.post("/public/ask", json={"question": "x" * 501})
        assert response.status_code == 422

    def test_public_only_app_does_not_mount_internal_routes(self):
        from rag_app.public_main import app as public_app

        with TestClient(public_app) as public_client:
            assert public_client.get("/public/health").status_code == 200
            assert public_client.post("/ask", json={"question": "x"}).status_code == 404
            assert public_client.post("/search", json={"query": "x"}).status_code == 404
            assert public_client.post("/ingest", json={}).status_code == 404
            assert public_client.post("/ingest/preview", json={}).status_code == 404
            assert public_client.get("/index/stats").status_code == 404
            assert public_client.get("/demo").status_code == 404
            assert public_client.get("/docs").status_code == 404
            assert public_client.get("/openapi.json").status_code == 404
