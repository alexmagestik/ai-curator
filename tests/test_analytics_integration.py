from __future__ import annotations

import pytest

from app.analytics.export import (
    export_daily_stats_csv,
    export_query_logs_csv,
    export_user_stats_csv,
)
from app.analytics.logger import RequestLogger
from app.analytics.metrics import AnalyticsService
from app.analytics.repository import QueryLogRepository
from app.auth.service import AuthService
from app.database.db import get_connection, init_db
from app.database.repository import UserRepository


@pytest.fixture
def analytics_env(settings):
    init_db(settings)
    user = AuthService(UserRepository(settings)).register("a@example.com", "pass1234").user
    repo = QueryLogRepository(settings)
    logger = RequestLogger(repo)
    logger.log(
        user_id=user.id,
        question="Что такое Python?",
        answer="Python — язык программирования.",
        metrics=logger.build_metrics(
            question="Что такое Python?",
            answer="Python — язык программирования.",
            response_time=1.2,
            response_type="rag",
            retrieved_documents=[],
        ),
        response_type="rag",
    )
    return settings, user.id


def test_query_log_repository(analytics_env) -> None:
    settings, _ = analytics_env
    logs = QueryLogRepository(settings).list_logs(limit=10)
    assert len(logs) == 1
    assert logs[0].question_category == "course_content"


def test_analytics_summary(analytics_env) -> None:
    settings, _ = analytics_env
    summary = AnalyticsService(QueryLogRepository(settings)).get_summary()
    assert summary.total_requests == 1
    assert summary.active_users == 1


def test_csv_exports(analytics_env) -> None:
    settings, _ = analytics_env
    service = AnalyticsService(QueryLogRepository(settings))
    assert "timestamp" in export_query_logs_csv(QueryLogRepository(settings))
    assert "date" in export_daily_stats_csv(service)
    assert "email" in export_user_stats_csv(service)


def test_analytics_summary_respects_date_range(analytics_env) -> None:
    settings, user_id = analytics_env
    repo = QueryLogRepository(settings)
    service = AnalyticsService(repo)

    from datetime import date, timedelta

    today = date.today()
    yesterday = today - timedelta(days=1)

    with get_connection(settings) as connection:
        connection.execute(
            """
            INSERT INTO query_logs (
                timestamp, user_id, question, answer, question_category,
                response_time, tokens_input, tokens_output, sources_count,
                answer_found, module, response_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{yesterday.isoformat()}T10:00:00+00:00",
                user_id,
                "Старый вопрос",
                "Старый ответ",
                "course_content",
                1.0,
                10,
                20,
                1,
                1,
                "module_01",
                "rag",
            ),
        )
        connection.commit()

    week_start = today - timedelta(days=6)
    week_summary = service.get_summary(week_start, today)
    assert week_summary.total_requests == 1

    old_only = service.get_summary(yesterday, yesterday)
    assert old_only.total_requests == 1

    empty = service.get_summary(today - timedelta(days=30), today - timedelta(days=8))
    assert empty.total_requests == 0
