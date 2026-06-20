"""Streamlit page for browsing and continuing chat sessions."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from app.auth.session import get_current_user, logout
from app.services.chat_service import ChatService


@st.cache_resource
def get_chat_service() -> ChatService:
    return ChatService()


def _format_datetime(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def render_dialogs_page() -> None:
    user = get_current_user()
    if user is None:
        return

    st.title("Мои диалоги")
    st.caption("Список ваших сессий. Можно искать по тексту сообщений и продолжить диалог.")

    service = get_chat_service()

    with st.sidebar:
        st.markdown(f"**{user.email}**")
        if st.button("Выйти", use_container_width=True):
            logout()
            st.rerun()

    search_query = st.text_input("Поиск по сообщениям", placeholder="Python, REST API...")
    sessions = service.search_sessions(user.id, search_query)

    if not sessions:
        st.info("Диалогов пока нет. Перейдите в «Чат» и задайте первый вопрос.")
        return

    for session in sessions:
        with st.container(border=True):
            col_info, col_action = st.columns([4, 1])
            with col_info:
                st.markdown(f"**{session.title}**")
                st.caption(
                    f"ID: {session.id} · "
                    f"Сообщений: {session.message_count} · "
                    f"Начат: {_format_datetime(session.started_at)}"
                )
            with col_action:
                if st.button("Продолжить", key=f"continue_{session.id}"):
                    st.session_state.current_session_id = session.id
                    st.session_state.pop("loaded_session_id", None)
                    st.session_state.chat_messages = service.load_session_messages(
                        session.id,
                        user.id,
                    )
                    st.session_state.active_page = "Чат"
                    st.rerun()
