from __future__ import annotations

from dataclasses import dataclass

from app.analytics.repository import QueryLogRepository
from app.database.db import get_connection
from app.utils.config import Settings, get_settings


@dataclass(frozen=True)
class AnalyticsSummary:
    total_requests: int
    active_users: int
    avg_response_time: float
    unanswered_rate: float
    top_categories: list[tuple[str, int]]
    top_modules: list[tuple[str, int]]
    requests_by_day: list[tuple[str, int]]


class AnalyticsService:
    def __init__(
        self,
        repository: QueryLogRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        if repository is not None:
            self.repository = repository
            self.settings = settings or repository.settings
        else:
            self.settings = settings or get_settings()
            self.repository = QueryLogRepository(self.settings)

    def get_summary(self) -> AnalyticsSummary:
        with get_connection(self.settings) as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_requests,
                    COUNT(DISTINCT user_id) AS active_users,
                    AVG(response_time) AS avg_response_time,
                    AVG(CASE WHEN answer_found = 0 THEN 1.0 ELSE 0.0 END) AS unanswered_rate
                FROM query_logs
                """
            ).fetchone()

            category_rows = connection.execute(
                """
                SELECT question_category, COUNT(*) AS cnt
                FROM query_logs
                GROUP BY question_category
                ORDER BY cnt DESC
                LIMIT 10
                """
            ).fetchall()

            module_rows = connection.execute(
                """
                SELECT module, COUNT(*) AS cnt
                FROM query_logs
                WHERE module IS NOT NULL AND module != ''
                GROUP BY module
                ORDER BY cnt DESC
                LIMIT 10
                """
            ).fetchall()

            day_rows = connection.execute(
                """
                SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS cnt
                FROM query_logs
                GROUP BY day
                ORDER BY day ASC
                """
            ).fetchall()

        return AnalyticsSummary(
            total_requests=int(totals["total_requests"] or 0),
            active_users=int(totals["active_users"] or 0),
            avg_response_time=float(totals["avg_response_time"] or 0.0),
            unanswered_rate=float(totals["unanswered_rate"] or 0.0),
            top_categories=[(row["question_category"], row["cnt"]) for row in category_rows],
            top_modules=[(row["module"], row["cnt"]) for row in module_rows],
            requests_by_day=[(row["day"], row["cnt"]) for row in day_rows],
        )

    def popular_documents(self, limit: int = 10) -> list[tuple[str, int]]:
        """Approximate popular documents via module mentions in logs."""
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT module, COUNT(*) AS cnt
                FROM query_logs
                WHERE module IS NOT NULL
                GROUP BY module
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [(row["module"], row["cnt"]) for row in rows]

    def user_statistics(self) -> list[dict]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT
                    u.email,
                    COUNT(l.id) AS requests,
                    AVG(l.response_time) AS avg_response_time,
                    MAX(l.timestamp) AS last_request
                FROM users u
                LEFT JOIN query_logs l ON l.user_id = u.id
                GROUP BY u.id, u.email
                ORDER BY requests DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def daily_report(self) -> list[dict]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT
                    substr(timestamp, 1, 10) AS date,
                    COUNT(*) AS requests,
                    COUNT(DISTINCT user_id) AS users,
                    AVG(response_time) AS avg_response_time
                FROM query_logs
                GROUP BY date
                ORDER BY date ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]
