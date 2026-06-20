from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.utils.config import Settings, get_settings


def get_llm(settings: Settings | None = None) -> BaseChatModel:
    """Return a chat model based on LLM_PROVIDER (.env)."""
    settings = settings or get_settings()

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to .env before using the chat."
            )
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
        )

    raise NotImplementedError(
        f"LLM provider '{settings.llm_provider}' is not implemented yet. "
        "Supported: openai. Planned: anthropic, gemini, ollama."
    )
