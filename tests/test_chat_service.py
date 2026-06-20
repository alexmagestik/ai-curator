from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from app.auth.service import AuthService
from app.database.db import init_db
from app.database.repository import UserRepository
from app.rag.pipeline import RAGResponse
from app.services.chat_service import ChatService
from app.services.level_detector import LevelDetectionResult


@pytest.fixture
def chat_service(settings) -> ChatService:
    init_db(settings)
    user = AuthService(UserRepository(settings)).register("s@example.com", "pass1234").user

    mock_pipeline = MagicMock()
    mock_pipeline.ask.return_value = RAGResponse(
        answer="RAG answer",
        sources=[],
        retrieved_documents=[],
        context="ctx",
    )

    mock_lms = MagicMock()
    mock_lms.answer.return_value = "Deadline is 2026-07-10"

    mock_detector = MagicMock()
    mock_detector.detect.return_value = LevelDetectionResult(
        level="beginner",
        confidence=0.8,
    )

    service = ChatService(
        pipeline=mock_pipeline,
        user_repository=UserRepository(settings),
        level_detector=mock_detector,
        lms_handler=mock_lms,
        settings=settings,
    )
    service._test_user_id = user.id
    return service


def test_chat_service_routes_knowledge_to_rag(chat_service: ChatService) -> None:
    result = chat_service.send_message(
        user_id=chat_service._test_user_id,
        session_id=None,
        question="Что такое Python?",
    )
    assert result.response_type == "rag"
    chat_service.pipeline.ask.assert_called_once()
    chat_service.lms_handler.answer.assert_not_called()


def test_chat_service_routes_organizational_to_lms(chat_service: ChatService) -> None:
    result = chat_service.send_message(
        user_id=chat_service._test_user_id,
        session_id=None,
        question="Когда дедлайн домашней работы?",
    )
    assert result.response_type == "lms"
    assert "2026-07-10" in result.answer
    chat_service.lms_handler.answer.assert_called_once()
    chat_service.pipeline.ask.assert_not_called()


def test_chat_service_updates_user_level(chat_service: ChatService) -> None:
    chat_service.send_message(
        user_id=chat_service._test_user_id,
        session_id=None,
        question="Когда дедлайн?",
    )
    profile = chat_service.users.get_profile(chat_service._test_user_id)
    assert profile is not None
    assert profile.current_level == "beginner"
    assert profile.confidence == 0.8
