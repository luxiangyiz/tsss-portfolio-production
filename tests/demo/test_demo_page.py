from fastapi.testclient import TestClient

from rag_app.main import app


client = TestClient(app)


def test_demo_page_returns_200_with_local_warning():
    response = client.get("/demo")
    assert response.status_code == 200
    assert "本页面仅在本机运行" in response.text
    assert "不代表真实语义检索和问答质量" in response.text
    assert "private scope可能包含个人敏感信息" in response.text


def test_demo_page_uses_scopes_not_collection_names():
    response = client.get("/demo")
    assert "kb_private" not in response.text
    assert "kb_internal" not in response.text
    assert "kb_public" not in response.text


def test_demo_page_has_security_headers():
    response = client.get("/demo")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_api_rejects_collection_name_as_public_scope():
    response = client.post(
        "/search",
        json={"query": "test", "index_scope": "kb_private", "top_k": 5},
    )
    assert response.status_code == 422
