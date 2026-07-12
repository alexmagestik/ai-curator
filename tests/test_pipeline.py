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


def test_pipeline_compare_prompts_retrieves_once_and_varies_system_prompt() -> None:
    retrieved = [
        RetrievedDocument(
            document=Document(
                page_content="RAG combines retrieval with generation.",
                metadata={
                    "module": "module_02",
                    "file_name": "lecture_02.odt",
                    "resource_type": "lecture",
                    "source_path": "/tmp/lecture_02.odt",
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
    mock_llm.invoke.side_effect = [
        AIMessage(content="Answer A"),
        AIMessage(content="Answer B"),
    ]

    pipeline = RAGPipeline(retriever=mock_retriever, llm=mock_llm)
    response_a, response_b = pipeline.compare_prompts(
        "Что такое RAG?",
        "БАЗОВЫЙ ПРОМПТ A",
        "БАЗОВЫЙ ПРОМПТ B",
        user_level="intermediate",
    )

    assert response_a.answer == "Answer A"
    assert response_b.answer == "Answer B"
    # Retrieval must happen only once so both variants share the same context.
    mock_retriever.search.assert_called_once()
    assert response_a.context == response_b.context

    system_a = mock_llm.invoke.call_args_list[0][0][0][0].content
    system_b = mock_llm.invoke.call_args_list[1][0][0][0].content
    assert "БАЗОВЫЙ ПРОМПТ A" in system_a
    assert "БАЗОВЫЙ ПРОМПТ B" in system_b
