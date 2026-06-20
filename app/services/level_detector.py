from __future__ import annotations

import json
import re
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.rag.pipeline import USER_LEVELS
from app.services.llm_factory import get_llm
from app.utils.config import Settings, get_settings

ORGANIZATIONAL_KEYWORDS = (
    "дедлайн",
    "deadline",
    "расписан",
    "schedule",
    "занят",
    "урок",
    "lesson",
    "домашн",
    "задани",
    "assignment",
    "когда сда",
    "следующ",
    "курс",
    "course-info",
    "course info",
    "срок",
    "сдать",
)


def classify_intent(question: str) -> str:
    """Return 'organizational' or 'knowledge'."""
    normalized = question.lower()
    if any(keyword in normalized for keyword in ORGANIZATIONAL_KEYWORDS):
        return "organizational"
    return "knowledge"


@dataclass(frozen=True)
class LevelDetectionResult:
    level: str
    confidence: float


class LevelDetector:
    """Estimate student knowledge level from their message."""

    def __init__(
        self,
        settings: Settings | None = None,
        llm: BaseChatModel | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or get_llm(self.settings)

    def detect(
        self,
        message: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> LevelDetectionResult:
        history_text = ""
        for item in (chat_history or [])[-4:]:
            history_text += f"{item.get('role', 'user')}: {item.get('content', '')}\n"

        prompt = (
            "Оцени уровень знаний студента по его сообщению.\n"
            "Уровни: beginner, intermediate, advanced.\n"
            "Верни ТОЛЬКО JSON без markdown:\n"
            '{"level": "intermediate", "confidence": 0.82}\n\n'
            f"История:\n{history_text}\n"
            f"Сообщение студента: {message}"
        )

        try:
            response = self.llm.invoke(
                [
                    SystemMessage(content="Ты классификатор уровня знаний студента."),
                    HumanMessage(content=prompt),
                ]
            )
            raw = response.content if isinstance(response, AIMessage) else str(response)
            parsed = _parse_json(raw)
            level = str(parsed.get("level", "intermediate")).lower()
            confidence = float(parsed.get("confidence", 0.5))
            if level not in USER_LEVELS:
                level = "intermediate"
            confidence = min(max(confidence, 0.0), 1.0)
            return LevelDetectionResult(level=level, confidence=confidence)
        except (ValueError, TypeError, json.JSONDecodeError):
            return LevelDetectionResult(level="intermediate", confidence=0.5)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def update_user_level(
    user_repository,
    user_id: int,
    detection: LevelDetectionResult,
):
    """Persist detected level to user profile."""
    return user_repository.update_user_level(
        user_id=user_id,
        level=detection.level,
        confidence=detection.confidence,
    )
