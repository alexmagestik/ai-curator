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
from app.database.db import init_db
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
