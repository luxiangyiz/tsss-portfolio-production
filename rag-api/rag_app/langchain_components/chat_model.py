"""Chat Model 工厂。"""

from langchain_openai import ChatOpenAI

from rag_app.core.config import get_default_llm_kwargs, settings


def create_chat_model():
    if settings.rag_runtime_mode == "offline_demo":
        if not settings.allow_fake_mode:
            raise RuntimeError("Fake chat model is disabled")
        from rag_app.demo.dependencies import create_demo_chat_model

        return create_demo_chat_model()

    kwargs = get_default_llm_kwargs()
    return ChatOpenAI(**kwargs)
