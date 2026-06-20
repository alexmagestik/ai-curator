from __future__ import annotations

from app.services.level_detector import classify_intent

ORGANIZATIONAL_SUBCATEGORIES = {
    "deadline": ("дедлайн", "deadline", "срок", "сдать"),
    "schedule": ("распис", "занят", "урок", "lesson", "следующ"),
    "assignment": ("задани", "assignment", "домашн", "homework"),
}


def categorize_question(question: str) -> str:
    intent = classify_intent(question)
    if intent != "organizational":
        return "course_content"

    normalized = question.lower()
    for category, keywords in ORGANIZATIONAL_SUBCATEGORIES.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "organizational"


def estimate_tokens(text: str) -> int:
    return max(len(text.split()), len(text) // 4)


def detect_answer_found(answer: str, sources_count: int, response_type: str) -> bool:
    if response_type == "lms":
        negative_markers = (
            "нет данных",
            "не найден",
            "недостаточно",
            "не могу",
            "отсутств",
        )
        lowered = answer.lower()
        return not any(marker in lowered for marker in negative_markers)

    if sources_count == 0:
        return False

    negative_markers = ("нет данных", "недостаточно данных", "не найдено в контексте")
    lowered = answer.lower()
    return not any(marker in lowered for marker in negative_markers)


def extract_primary_module(retrieved_documents) -> str | None:
    if not retrieved_documents:
        return None
    return retrieved_documents[0].document.metadata.get("module")
