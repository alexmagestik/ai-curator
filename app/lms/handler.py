from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.lms.client import LMSClient
from app.prompts.loader import build_system_prompt
from app.rag.pipeline import USER_LEVELS
from app.services.llm_factory import get_llm
from app.utils.config import Settings, get_settings


class LMSHandler:
    """Answer organizational questions using LMS data (not RAG)."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: LMSClient | None = None,
        llm: BaseChatModel | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or LMSClient(self.settings)
        self.llm = llm or get_llm(self.settings)

    def answer(
        self,
        question: str,
        *,
        user_level: str = "intermediate",
        chat_history: list[dict[str, str]] | None = None,
    ) -> str:
        if user_level not in USER_LEVELS:
            user_level = "intermediate"

        lms_context = json.dumps(self.client.get_all_context(), ensure_ascii=False, indent=2)
        system_prompt = build_system_prompt(user_level=user_level)

        messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=system_prompt),
            SystemMessage(
                content=(
                    "Ты отвечаешь на организационные вопросы студента по курсу.\n"
                    "Используй ТОЛЬКО данные LMS ниже. Не используй базу знаний лекций.\n"
                    "Если информации нет в LMS — сообщи об этом.\n\n"
                    f"Данные LMS:\n{lms_context}"
                )
            ),
        ]

        for item in (chat_history or [])[-6:]:
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
                    f"Вопрос студента: {question}\n\n"
                    "Ответь по расписанию, дедлайнам или заданиям на основе LMS."
                )
            )
        )

        response = self.llm.invoke(messages)
        return response.content if isinstance(response, AIMessage) else str(response)
