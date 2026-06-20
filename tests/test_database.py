from __future__ import annotations

import pytest

from app.auth.service import AuthError, AuthService
from app.database.db import init_db
from app.database.repository import ChatRepository, UserRepository


@pytest.fixture
def auth_service(settings) -> AuthService:
    init_db(settings)
    return AuthService(UserRepository(settings))


def test_register_and_login(auth_service: AuthService) -> None:
    auth_service.register("student@example.com", "password123")
    result = auth_service.login("student@example.com", "password123")
    assert result.user.email == "student@example.com"
    assert result.user.role == "user"


def test_register_duplicate_email(auth_service: AuthService) -> None:
    auth_service.register("student@example.com", "password123")
    with pytest.raises(AuthError):
        auth_service.register("student@example.com", "otherpass")


def test_login_invalid_password(auth_service: AuthService) -> None:
    auth_service.register("student@example.com", "password123")
    with pytest.raises(AuthError):
        auth_service.login("student@example.com", "wrong")


def test_chat_repository_persists_messages(settings) -> None:
    init_db(settings)
    users = UserRepository(settings)
    chats = ChatRepository(settings)

    user = users.create_user("student@example.com", "hash", role="user")
    session = chats.create_session(user.id, title="Test")
    chats.add_message(session.id, "user", "What is Python?")
    chats.add_message(session.id, "assistant", "Python is a programming language.")

    messages = chats.get_messages(session.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"

    found = chats.search_sessions(user.id, "Python")
    assert len(found) == 1
    assert found[0].id == session.id
