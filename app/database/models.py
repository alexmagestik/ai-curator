from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class User:
    id: int
    email: str
    role: str
    created_at: str


@dataclass(frozen=True)
class UserSummary:
    id: int
    email: str
    role: str
    created_at: str
    current_level: str
    session_count: int
    last_activity: str | None


@dataclass(frozen=True)
class UserProfile:
    user_id: int
    current_level: str
    confidence: float
    updated_at: str


@dataclass(frozen=True)
class ChatSession:
    id: int
    user_id: int
    title: str
    started_at: str
    message_count: int = 0


@dataclass(frozen=True)
class Message:
    id: int
    session_id: int
    role: str
    content: str
    created_at: str
