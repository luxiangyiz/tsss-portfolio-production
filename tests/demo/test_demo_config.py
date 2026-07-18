import pytest

from rag_app.core.config import (
    get_effective_relevance_threshold,
    settings,
    validate_runtime_security,
)


def test_offline_demo_accepts_localhost(monkeypatch):
    monkeypatch.setattr(settings, "rag_runtime_mode", "offline_demo")
    monkeypatch.setattr(settings, "allow_fake_mode", True)
    monkeypatch.setattr(settings, "demo_host", "127.0.0.1")
    monkeypatch.setattr(settings, "api_host", "127.0.0.1")
    monkeypatch.setattr(settings, "cors_origins", "")
    validate_runtime_security()


@pytest.mark.parametrize("field", ["demo_host", "api_host"])
def test_offline_demo_rejects_public_binding(monkeypatch, field):
    monkeypatch.setattr(settings, "rag_runtime_mode", "offline_demo")
    monkeypatch.setattr(settings, "allow_fake_mode", True)
    monkeypatch.setattr(settings, "demo_host", "127.0.0.1")
    monkeypatch.setattr(settings, "api_host", "127.0.0.1")
    monkeypatch.setattr(settings, "cors_origins", "")
    monkeypatch.setattr(settings, field, "0.0.0.0")
    with pytest.raises(ValueError, match="only bind"):
        validate_runtime_security()


def test_offline_demo_requires_explicit_fake_permission(monkeypatch):
    monkeypatch.setattr(settings, "rag_runtime_mode", "offline_demo")
    monkeypatch.setattr(settings, "allow_fake_mode", False)
    monkeypatch.setattr(settings, "demo_host", "127.0.0.1")
    monkeypatch.setattr(settings, "api_host", "127.0.0.1")
    monkeypatch.setattr(settings, "cors_origins", "")
    with pytest.raises(ValueError, match="ALLOW_FAKE_MODE"):
        validate_runtime_security()


def test_offline_demo_rejects_cors(monkeypatch):
    monkeypatch.setattr(settings, "rag_runtime_mode", "offline_demo")
    monkeypatch.setattr(settings, "allow_fake_mode", True)
    monkeypatch.setattr(settings, "demo_host", "127.0.0.1")
    monkeypatch.setattr(settings, "api_host", "127.0.0.1")
    monkeypatch.setattr(settings, "cors_origins", "https://example.com")
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        validate_runtime_security()


def test_offline_demo_uses_zero_relevance_threshold(monkeypatch):
    monkeypatch.setattr(settings, "rag_runtime_mode", "offline_demo")
    monkeypatch.setattr(settings, "relevance_threshold", 0.3)
    assert get_effective_relevance_threshold() == 0.0


def test_real_local_keeps_configured_relevance_threshold(monkeypatch):
    monkeypatch.setattr(settings, "rag_runtime_mode", "real_local")
    monkeypatch.setattr(settings, "relevance_threshold", 0.3)
    assert get_effective_relevance_threshold() == 0.3
