from __future__ import annotations

from dataclasses import dataclass

from app.database.models import utc_now_iso


@dataclass(frozen=True)
class QueryLog:
    id: int
    timestamp: str
    user_id: int
    question: str
    answer: str
    question_category: str
    response_time: float
    tokens_input: int
    tokens_output: int
    sources_count: int
    answer_found: bool
    module: str | None
    response_type: str
    user_email: str | None = None
