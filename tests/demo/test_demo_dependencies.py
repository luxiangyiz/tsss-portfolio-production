from rag_app.core.config import settings
from rag_app.demo.dependencies import DemoChatModel, DemoEmbeddings


def test_demo_dependencies_are_application_owned():
    assert DemoEmbeddings.__module__.startswith("rag_app.demo")
    assert DemoChatModel.__module__.startswith("rag_app.demo")


def test_offline_factory_uses_demo_models(monkeypatch):
    monkeypatch.setattr(settings, "rag_runtime_mode", "offline_demo")
    monkeypatch.setattr(settings, "allow_fake_mode", True)
    monkeypatch.setattr(settings, "embedding_dimension", 128)

    from rag_app.langchain_components.embeddings import create_embeddings
    from rag_app.langchain_components.chat_model import create_chat_model

    assert isinstance(create_embeddings(), DemoEmbeddings)
    assert isinstance(create_chat_model(), DemoChatModel)
    assert len(create_embeddings().embed_query("测试")) == 128


def test_real_local_factory_does_not_load_demo(monkeypatch):
    monkeypatch.setattr(settings, "rag_runtime_mode", "real_local")
    sentinel = object()
    monkeypatch.setattr(
        "rag_app.langchain_components.embeddings.OpenAIEmbeddings",
        lambda **kwargs: sentinel,
    )
    from rag_app.langchain_components.embeddings import create_embeddings

    assert create_embeddings() is sentinel
