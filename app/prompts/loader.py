from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent

LEVEL_INSTRUCTIONS = {
    "beginner": (
        "Уровень студента: Beginner.\n"
        "Используй простые объяснения, минимум терминов, приводи примеры."
    ),
    "intermediate": (
        "Уровень студента: Intermediate.\n"
        "Дай умеренную техническую глубину и поясняй термины при первом упоминании."
    ),
    "advanced": (
        "Уровень студента: Advanced.\n"
        "Используй профессиональную терминологию и технические детали."
    ),
}


@lru_cache
def load_system_prompt() -> str:
    return (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()


@lru_cache
def load_fewshot_examples() -> dict:
    path = PROMPTS_DIR / "fewshot_examples.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def format_fewshot_block() -> str:
    examples = load_fewshot_examples()
    lines = ["Примеры корректных ответов:"]

    for index, item in enumerate(examples.get("correct", [])[:3], start=1):
        lines.append(
            f"{index}. Вопрос: {item['question']}\n"
            f"   Ответ: {item['answer']}"
        )

    lines.append("\nПримеры некорректных ответов (так делать нельзя):")
    for index, item in enumerate(examples.get("incorrect", [])[:3], start=1):
        lines.append(
            f"{index}. Вопрос: {item['question']}\n"
            f"   Плохой ответ: {item['bad_answer']}\n"
            f"   Почему: {item['reason']}"
        )

    return "\n".join(lines)


def build_system_prompt(user_level: str = "intermediate") -> str:
    level_block = LEVEL_INSTRUCTIONS.get(user_level, LEVEL_INSTRUCTIONS["intermediate"])
    return (
        f"{load_system_prompt()}\n\n"
        f"{level_block}\n\n"
        f"{format_fewshot_block()}"
    )
