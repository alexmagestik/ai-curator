from __future__ import annotations

import csv
import io
from datetime import date, datetime

from app.analytics.metrics import AnalyticsService
from app.analytics.repository import QueryLogRepository


def export_query_logs_csv(
    repository: QueryLogRepository | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    repository = repository or QueryLogRepository()
    logs = repository.fetch_all_for_export(start_date, end_date)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "timestamp",
            "user",
            "question",
            "answer",
            "category",
            "response_time",
            "tokens_input",
            "tokens_output",
            "sources_count",
            "answer_found",
            "module",
            "response_type",
        ]
    )
    for log in logs:
        writer.writerow(
            [
                log.timestamp,
                log.user_email or log.user_id,
                log.question,
                log.answer,
                log.question_category,
                f"{log.response_time:.3f}",
                log.tokens_input,
                log.tokens_output,
                log.sources_count,
                int(log.answer_found),
                log.module or "",
                log.response_type,
            ]
        )
    return buffer.getvalue()


def export_daily_stats_csv(
    service: AnalyticsService | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    service = service or AnalyticsService()
    rows = service.daily_report(start_date, end_date)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", "requests", "users", "avg_response_time"])
    for row in rows:
        writer.writerow(
            [
                row["date"],
                row["requests"],
                row["users"],
                f"{float(row['avg_response_time'] or 0.0):.3f}",
            ]
        )
    return buffer.getvalue()


def export_user_stats_csv(
    service: AnalyticsService | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    service = service or AnalyticsService()
    rows = service.user_statistics(start_date, end_date)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["email", "requests", "avg_response_time", "last_request"])
    for row in rows:
        writer.writerow(
            [
                row["email"],
                row["requests"],
                f"{float(row['avg_response_time'] or 0.0):.3f}",
                row["last_request"] or "",
            ]
        )
    return buffer.getvalue()


def export_filename(prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.csv"
