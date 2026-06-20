"""Analytics dashboard and CSV export (admin)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.analytics.export import (
    export_daily_stats_csv,
    export_filename,
    export_query_logs_csv,
    export_user_stats_csv,
)
from app.analytics.metrics import AnalyticsService
from app.analytics.repository import QueryLogRepository
from app.auth.session import is_admin


def render_analytics_page() -> None:
    if not is_admin():
        st.error("Доступ только для администратора.")
        return

    st.title("Аналитика")
    st.caption("Метрики качества системы и экспорт отчётов.")

    service = AnalyticsService()
    summary = service.get_summary()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Всего запросов", summary.total_requests)
    c2.metric("Активных пользователей", summary.active_users)
    c3.metric("Среднее время ответа", f"{summary.avg_response_time:.2f}s")
    c4.metric("Запросы без ответа", f"{summary.unanswered_rate:.0%}")

    if summary.requests_by_day:
        df_days = pd.DataFrame(summary.requests_by_day, columns=["date", "requests"])
        fig = px.line(df_days, x="date", y="requests", title="Запросы по дням")
        st.plotly_chart(fig, use_container_width=True)

    col_left, col_right = st.columns(2)
    with col_left:
        if summary.top_categories:
            df_cat = pd.DataFrame(summary.top_categories, columns=["category", "count"])
            fig_cat = px.bar(df_cat, x="category", y="count", title="Популярные темы")
            st.plotly_chart(fig_cat, use_container_width=True)
    with col_right:
        if summary.top_modules:
            df_mod = pd.DataFrame(summary.top_modules, columns=["module", "count"])
            fig_mod = px.bar(df_mod, x="module", y="count", title="Популярные модули")
            st.plotly_chart(fig_mod, use_container_width=True)

    st.subheader("Экспорт CSV")
    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button(
            "Выгрузить запросы",
            data=export_query_logs_csv(),
            file_name=export_filename("query_logs"),
            mime="text/csv",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "Выгрузить статистику по дням",
            data=export_daily_stats_csv(service),
            file_name=export_filename("daily_stats"),
            mime="text/csv",
            use_container_width=True,
        )
    with e3:
        st.download_button(
            "Выгрузить статистику пользователей",
            data=export_user_stats_csv(service),
            file_name=export_filename("user_stats"),
            mime="text/csv",
            use_container_width=True,
        )

    st.subheader("Последние запросы")
    logs = QueryLogRepository().list_logs(limit=50)
    if logs:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "timestamp": log.timestamp,
                        "user": log.user_email,
                        "question": log.question[:120],
                        "category": log.question_category,
                        "response_time": round(log.response_time, 3),
                        "tokens": log.tokens_input + log.tokens_output,
                        "sources": log.sources_count,
                        "answer_found": log.answer_found,
                    }
                    for log in logs
                ]
            ),
            use_container_width=True,
        )
    else:
        st.info("Логов пока нет.")
