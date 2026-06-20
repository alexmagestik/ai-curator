from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.prompts.loader import build_system_prompt
from app.rag.context import SourceReference, build_context, extract_sources
from app.rag.retriever import HybridRetriever, RetrievedDocument
from app.services.llm_factory import get_llm
from app.utils.config import Settings, get_settings

USER_LEVELS = ("beginner", "intermediate", "advanced")


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    sources: list[SourceReference]
    retrieved_documents: list[RetrievedDocument]
    context: str
    tokens_input: int = 0
    tokens_output: int = 0


@dataclass(frozen=True)
class RAGDebugResult:
    question: str
    retrieved_documents: list[RetrievedDocument]
    context: str
    answer: str
    user_level: str


class RAGPipeline:
    """Question → hybrid search → context → LLM → answer with sources."""

    def __init__(
        self,
        settings: Settings | None = None,
        retriever: HybridRetriever | None = None,
        llm: BaseChatModel | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or HybridRetriever(self.settings)
        self.llm = llm or get_llm(self.settings)

    def ask(
        self,
        question: str,
        *,
        user_level: str = "intermediate",
        filters: dict[str, str] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        max_history_messages: int = 10,
    ) -> RAGResponse:
        if user_level not in USER_LEVELS:
            user_level = "intermediate"

        retrieved = self.retriever.search(question, filters=filters)
        context = build_context(retrieved)
        sources = extract_sources(retrieved)
        system_prompt = build_system_prompt(user_level=user_level)

        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=system_prompt)
        ]

        history = (chat_history or [])[-max_history_messages:]
        for item in history:
            role = item.get("role", "")
            content = item.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        messages.append(
            HumanMessage(
                content=(
                    f"Контекст из материалов курса:\n\n{context}\n\n"
                    f"Текущий вопрос студента: {question}\n\n"
                    "Учитывай историю диалога выше. "
                    "Ответь на текущий вопрос, опираясь только на контекст курса. "
                    "Если данных недостаточно — прямо сообщи об этом. "
                    "В конце ответа перечисли использованные источники "
                    "(модуль и название документа)."
                )
            )
        )

        response = self.llm.invoke(messages)
        answer = response.content if isinstance(response, AIMessage) else str(response)
        tokens_input, tokens_output = _extract_token_usage(response, messages, answer)

        return RAGResponse(
            answer=answer,
            sources=sources,
            retrieved_documents=retrieved,
            context=context,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )

    def debug(
        self,
        question: str,
        *,
        user_level: str = "intermediate",
        filters: dict[str, str] | None = None,
    ) -> RAGDebugResult:
        response = self.ask(
            question,
            user_level=user_level,
            filters=filters,
            chat_history=[],
            max_history_messages=0,
        )
        return RAGDebugResult(
            question=question,
            retrieved_documents=response.retrieved_documents,
            context=response.context,
            answer=response.answer,
            user_level=user_level,
        )


def _extract_token_usage(
    response: AIMessage,
    messages: list,
    answer: str,
) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None)
    if usage:
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        if input_tokens or output_tokens:
            return input_tokens, output_tokens

    meta = getattr(response, "response_metadata", {}) or {}
    token_usage = meta.get("token_usage") or meta.get("usage") or {}
    input_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
    output_tokens = int(token_usage.get("completion_tokens", 0) or 0)
    if input_tokens or output_tokens:
        return input_tokens, output_tokens

    from app.analytics.categories import estimate_tokens

    prompt_text = "\n".join(getattr(message, "content", "") for message in messages)
    return estimate_tokens(prompt_text), estimate_tokens(answer)
