"""Streamlit chat page."""

from __future__ import annotations

import streamlit as st

from app.auth.session import get_current_user, logout
from app.database.repository import UserRepository
from app.services.chat_service import ChatService
from app.utils.config import get_settings


@st.cache_resource
def get_chat_service() -> ChatService:
    return ChatService()


def _ensure_chat_messages_loaded(session_id: int, user_id: int) -> None:
    if st.session_state.get("loaded_session_id") == session_id:
        return
    service = get_chat_service()
    st.session_state.chat_messages = service.load_session_messages(session_id, user_id)
    st.session_state.loaded_session_id = session_id


def render_chat_page() -> None:
    settings = get_settings()
    user = get_current_user()
    if user is None:
        return

    st.title("Чат с ИИ-куратором")
    st.caption(
        "Учебные вопросы — через RAG. Организационные (дедлайны, расписание) — через LMS API."
    )

    if not settings.openai_api_key:
        st.error("Укажите OPENAI_API_KEY в файле `.env` для работы чата.")
        return

    service = get_chat_service()
    user_repo = UserRepository()
    profile = user_repo.get_profile(user.id)

    modules = ["Все модули", *service.pipeline.retriever.available_modules]

    with st.sidebar:
        st.markdown(f"**{user.email}**")
        st.caption(f"Роль: {user.role}")
        if profile:
            st.info(
                f"Уровень: **{profile.current_level.capitalize()}**  \n"
                f"Уверенность: {profile.confidence:.0%}"
            )
        if st.button("Выйти", use_container_width=True):
            logout()
            st.rerun()

        st.divider()
        st.header("Настройки")
        st.caption("Уровень определяется автоматически после каждого сообщения.")
        selected_module = st.selectbox("Фильтр по модулю (только RAG)", options=modules)

        if st.button("Новый диалог", use_container_width=True):
            st.session_state.pop("current_session_id", None)
            st.session_state.pop("loaded_session_id", None)
            st.session_state.chat_messages = []
            st.rerun()

        st.divider()
        st.markdown("**Параметры**")
        st.text(f"LMS API: {settings.lms_api_url}")
        st.text(f"Top-K: {settings.top_k}")
        st.text(f"History: {settings.max_history_messages} сообщений")
        if st.button("Перезагрузить сервисы"):
            st.cache_resource.clear()
            st.rerun()

    session_id = st.session_state.get("current_session_id")
    if session_id is not None:
        _ensure_chat_messages_loaded(session_id, user.id)

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("response_type"):
                st.caption(f"Тип ответа: {message['response_type']}")
            if message.get("sources"):
                with st.expander("Источники"):
                    st.markdown(message["sources"])
            if message.get("fragments"):
                with st.expander("Найденные фрагменты"):
                    st.markdown(message["fragments"])

    if prompt := st.chat_input("Ваш вопрос..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        filters: dict[str, str] = {}
        if selected_module != "Все модули":
            filters["module"] = selected_module

        with st.chat_message("assistant"):
            with st.spinner("Формирую ответ..."):
                try:
                    result = service.send_message(
                        user_id=user.id,
                        session_id=st.session_state.get("current_session_id"),
                        question=prompt,
                        filters=filters or None,
                    )
                except Exception as exc:
                    st.error(f"Ошибка при генерации ответа: {exc}")
                    return

            type_label = "LMS" if result.response_type == "lms" else "RAG"
            st.caption(f"Тип ответа: {type_label}")
            st.markdown(result.answer)
            st.markdown(result.sources_text)

            with st.expander("Источники"):
                st.markdown(result.sources_text)
            if result.response_type == "rag":
                with st.expander("Найденные фрагменты"):
                    st.markdown(result.fragments_text)

        st.session_state.current_session_id = result.session.id
        st.session_state.loaded_session_id = result.session.id
        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": result.answer,
                "response_type": result.response_type,
                "sources": result.sources_text,
                "fragments": result.fragments_text if result.response_type == "rag" else None,
            }
        )
        st.rerun()
