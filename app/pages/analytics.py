"""Analytics dashboard and CSV export (admin)."""

from __future__ import annotations

from datetime import date, timedelta

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


def _init_period_defaults() -> None:
    today = date.today()
    if "analytics_start" not in st.session_state:
        st.session_state.analytics_start = today - timedelta(days=6)
    if "analytics_end" not in st.session_state:
        st.session_state.analytics_end = today


def _apply_period_preset(preset: str) -> None:
    today = date.today()
    if preset == "Последняя неделя":
        st.session_state.analytics_start = today - timedelta(days=6)
        st.session_state.analytics_end = today
    elif preset == "Последний месяц":
        st.session_state.analytics_start = today - timedelta(days=29)
        st.session_state.analytics_end = today
    elif preset == "Сегодня":
        st.session_state.analytics_start = today
        st.session_state.analytics_end = today
    elif preset == "Всё время":
        st.session_state.analytics_start = None
        st.session_state.analytics_end = None


def _render_period_selector() -> tuple[date | None, date | None]:
    _init_period_defaults()

    st.subheader("Период отчёта")
    preset = st.selectbox(
        "Быстрый выбор",
        options=["Последняя неделя", "Последний месяц", "Сегодня", "Всё время", "Произвольный"],
        index=0,
        key="analytics_preset",
    )

    if preset != "Произвольный":
        _apply_period_preset(preset)
        start_date = st.session_state.analytics_start
        end_date = st.session_state.analytics_end
        if start_date and end_date:
            st.caption(f"Данные с **{start_date.strftime('%d.%m.%Y')}** по **{end_date.strftime('%d.%m.%Y')}**")
        else:
            st.caption("Данные за всё время")
        return start_date, end_date

    today = date.today()
    col_start, col_end = st.columns(2)
    start_date = col_start.date_input(
        "С",
        value=st.session_state.analytics_start or today - timedelta(days=6),
        max_value=today,
        key="analytics_custom_start",
    )
    end_date = col_end.date_input(
        "По",
        value=st.session_state.analytics_end or today,
        min_value=start_date,
        max_value=today,
        key="analytics_custom_end",
    )
    st.session_state.analytics_start = start_date
    st.session_state.analytics_end = end_date
    return start_date, end_date


def render_analytics_page() -> None:
    if not is_admin():
        st.error("Доступ только для администратора.")
        return

    st.title("Аналитика")
    st.caption("Метрики качества системы и экспорт отчётов.")

    start_date, end_date = _render_period_selector()

    service = AnalyticsService()
    summary = service.get_summary(start_date, end_date)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Всего запросов", summary.total_requests)
    c2.metric("Активных пользователей", summary.active_users)
    c3.metric("Среднее время ответа", f"{summary.avg_response_time:.2f}s")
    c4.metric("Запросы без ответа", f"{summary.unanswered_rate:.0%}")

    if summary.requests_by_day:
        df_days = pd.DataFrame(summary.requests_by_day, columns=["date", "requests"])
        fig = px.line(df_days, x="date", y="requests", title="Запросы по дням")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("За выбранный период запросов нет.")

    col_left, col_right = st.columns(2)
    with col_left:
        if summary.top_categories:
            df_cat = pd.DataFrame(summary.top_categories, columns=["category", "count"])
            fig_cat = px.bar(df_cat, x="category", y="count", title="Популярные темы")
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("Нет данных по темам за выбранный период.")
    with col_right:
        if summary.top_modules:
            df_mod = pd.DataFrame(summary.top_modules, columns=["module", "count"])
            fig_mod = px.bar(df_mod, x="module", y="count", title="Популярные модули")
            st.plotly_chart(fig_mod, use_container_width=True)
        else:
            st.info("Нет данных по модулям за выбранный период.")

    st.subheader("Экспорт CSV")
    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button(
            "Выгрузить запросы",
            data=export_query_logs_csv(start_date=start_date, end_date=end_date),
            file_name=export_filename("query_logs"),
            mime="text/csv",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "Выгрузить статистику по дням",
            data=export_daily_stats_csv(service, start_date, end_date),
            file_name=export_filename("daily_stats"),
            mime="text/csv",
            use_container_width=True,
        )
    with e3:
        st.download_button(
            "Выгрузить статистику пользователей",
            data=export_user_stats_csv(service, start_date, end_date),
            file_name=export_filename("user_stats"),
            mime="text/csv",
            use_container_width=True,
        )

    st.subheader("Последние запросы")
    logs = QueryLogRepository().list_logs(limit=50, start_date=start_date, end_date=end_date)
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
        st.info("За выбранный период логов нет.")
