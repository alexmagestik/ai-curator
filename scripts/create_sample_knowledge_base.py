#!/usr/bin/env python3
"""Create sample ODT files for local development and manual testing."""

from __future__ import annotations

from pathlib import Path

from odf.opendocument import OpenDocumentText
from odf.text import P

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge_base"

SAMPLES: dict[str, dict[str, str]] = {
    "module_01": {
        "lecture_01.odt": (
            "Модуль 1. Введение в Python Backend.\n\n"
            "Python — высокоуровневый язык программирования. "
            "Backend-разработка включает создание серверной части приложений, "
            "работу с базами данных и REST API.\n\n"
            "Основные темы: переменные, функции, модули, виртуальные окружения."
        ),
        "faq.odt": (
            "Часто задаваемые вопросы по модулю 1.\n\n"
            "Вопрос: Как установить Python?\n"
            "Ответ: Скачайте дистрибутив с python.org и создайте виртуальное окружение.\n\n"
            "Вопрос: Что такое pip?\n"
            "Ответ: Менеджер пакетов Python для установки зависимостей."
        ),
    },
    "module_02": {
        "lecture_01.odt": (
            "Модуль 2. Работа с базами данных.\n\n"
            "SQLite — встроенная реляционная СУБД для прототипирования. "
            "ORM упрощает работу с таблицами и миграциями.\n\n"
            "Темы: SQL-запросы, индексы, транзакции, SQLAlchemy."
        ),
        "lecture_02.odt": (
            "Модуль 2. REST API и FastAPI.\n\n"
            "REST — архитектурный стиль для HTTP-сервисов. "
            "FastAPI обеспечивает быструю разработку API с автогенерацией документации."
        ),
    },
    "module_03": {
        "lecture_01.odt": (
            "Модуль 3. RAG и LLM.\n\n"
            "Retrieval-Augmented Generation объединяет поиск по базе знаний "
            "и генерацию ответов языковой моделью.\n\n"
            "Компоненты: эмбеддинги, векторное хранилище, retriever, prompt."
        ),
    },
}


def write_odt(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = OpenDocumentText()
    for paragraph in content.split("\n"):
        document.text.addElement(P(text=paragraph))
    document.save(str(path))


def main() -> None:
    for module, files in SAMPLES.items():
        for file_name, text in files.items():
            write_odt(KNOWLEDGE_BASE / module / file_name, text)
    print(f"Sample knowledge base created at {KNOWLEDGE_BASE}")


if __name__ == "__main__":
    main()
