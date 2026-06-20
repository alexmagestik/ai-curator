from __future__ import annotations

from app.analytics.models import QueryLog
from app.database.db import get_connection
from app.database.models import utc_now_iso
from app.utils.config import Settings, get_settings


class QueryLogRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def log_query(
        self,
        *,
        user_id: int,
        question: str,
        answer: str,
        question_category: str,
        response_time: float,
        tokens_input: int,
        tokens_output: int,
        sources_count: int,
        answer_found: bool,
        module: str | None,
        response_type: str,
    ) -> int:
        timestamp = utc_now_iso()
        with get_connection(self.settings) as connection:
            cursor = connection.execute(
                """
                INSERT INTO query_logs (
                    timestamp, user_id, question, answer, question_category,
                    response_time, tokens_input, tokens_output, sources_count,
                    answer_found, module, response_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    user_id,
                    question,
                    answer,
                    question_category,
                    response_time,
                    tokens_input,
                    tokens_output,
                    sources_count,
                    int(answer_found),
                    module,
                    response_type,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_logs(self, limit: int = 100) -> list[QueryLog]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT l.*, u.email AS user_email
                FROM query_logs l
                JOIN users u ON u.id = l.user_id
                ORDER BY l.timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_log(row) for row in rows]

    def fetch_all_for_export(self) -> list[QueryLog]:
        with get_connection(self.settings) as connection:
            rows = connection.execute(
                """
                SELECT l.*, u.email AS user_email
                FROM query_logs l
                JOIN users u ON u.id = l.user_id
                ORDER BY l.timestamp ASC
                """
            ).fetchall()
        return [self._row_to_log(row) for row in rows]

    @staticmethod
    def _row_to_log(row) -> QueryLog:
        return QueryLog(
            id=row["id"],
            timestamp=row["timestamp"],
            user_id=row["user_id"],
            question=row["question"],
            answer=row["answer"],
            question_category=row["question_category"],
            response_time=row["response_time"],
            tokens_input=row["tokens_input"],
            tokens_output=row["tokens_output"],
            sources_count=row["sources_count"],
            answer_found=bool(row["answer_found"]),
            module=row["module"],
            response_type=row["response_type"],
            user_email=row["user_email"],
        )
