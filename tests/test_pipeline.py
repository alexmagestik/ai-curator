from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from app.rag.pipeline import RAGPipeline
from app.rag.retriever import RetrievedDocument


def test_pipeline_ask_returns_answer_and_sources() -> None:
    retrieved = [
        RetrievedDocument(
            document=Document(
                page_content="Python virtual environments isolate dependencies.",
                metadata={
                    "module": "module_01",
                    "file_name": "lecture_01.odt",
                    "resource_type": "lecture",
                    "source_path": "/tmp/lecture_01.odt",
                    "chunk_index": "0",
                },
            ),
            score=1.0,
            source="vector",
        )
    ]

    mock_retriever = MagicMock()
    mock_retriever.search.return_value = retrieved

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="Виртуальное окружение изолирует зависимости проекта. "
        "Источник: module_01, lecture_01.odt."
    )

    pipeline = RAGPipeline(retriever=mock_retriever, llm=mock_llm)
    response = pipeline.ask("Что такое venv?", user_level="intermediate")

    assert "виртуальное окружение" in response.answer.lower()
    assert len(response.sources) == 1
    assert response.sources[0].module == "module_01"
    mock_retriever.search.assert_called_once()


def test_pipeline_uses_chat_history() -> None:
    retrieved = [
        RetrievedDocument(
            document=Document(
                page_content="Python virtual environments isolate dependencies.",
                metadata={
                    "module": "module_01",
                    "file_name": "lecture_01.odt",
                    "resource_type": "lecture",
                    "source_path": "/tmp/lecture_01.odt",
                    "chunk_index": "0",
                },
            ),
            score=1.0,
            source="vector",
        )
    ]

    mock_retriever = MagicMock()
    mock_retriever.search.return_value = retrieved

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="Follow-up answer.")

    pipeline = RAGPipeline(retriever=mock_retriever, llm=mock_llm)
    pipeline.ask(
        "Tell me more",
        chat_history=[
            {"role": "user", "content": "What is venv?"},
            {"role": "assistant", "content": "Virtual environment isolates packages."},
        ],
    )

    call_messages = mock_llm.invoke.call_args[0][0]
    roles = [message.__class__.__name__ for message in call_messages]
    assert roles.count("HumanMessage") >= 2
    assert "AIMessage" in roles
