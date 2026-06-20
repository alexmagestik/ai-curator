"""RAG debug page (admin)."""

from __future__ import annotations

import streamlit as st

from app.auth.session import is_admin
from app.rag.pipeline import RAGPipeline, USER_LEVELS
from app.utils.config import get_settings


@st.cache_resource
def get_pipeline() -> RAGPipeline:
    return RAGPipeline()


def render_rag_debug_page() -> None:
    if not is_admin():
        st.error("Доступ только для администратора.")
        return

    settings = get_settings()
    st.title("RAG Debug")
    st.caption("Пошаговая диагностика retrieval и генерации ответа.")

    if not settings.openai_api_key:
        st.error("Укажите OPENAI_API_KEY в `.env`.")
        return

    pipeline = get_pipeline()
    modules = ["Все модули", *pipeline.retriever.available_modules]

    question = st.text_area("Запрос", placeholder="Что такое RAG?")
    user_level = st.selectbox(
        "Уровень",
        options=list(USER_LEVELS),
        index=1,
        format_func=lambda value: value.capitalize(),
    )
    selected_module = st.selectbox("Фильтр по модулю", options=modules)

    if st.button("Запустить RAG Debug", type="primary"):
        if not question.strip():
            st.warning("Введите запрос.")
            return

        filters: dict[str, str] = {}
        if selected_module != "Все модули":
            filters["module"] = selected_module

        with st.spinner("Выполняю retrieval и генерацию..."):
            result = pipeline.debug(
                question.strip(),
                user_level=user_level,
                filters=filters or None,
            )

        st.markdown("### 1. Запрос")
        st.write(result.question)

        st.markdown("### 2. Полученные документы")
        if not result.retrieved_documents:
            st.info("Документы не найдены.")
        for index, item in enumerate(result.retrieved_documents, start=1):
            meta = item.document.metadata
            st.markdown(
                f"**{index}. {meta.get('file_name')}** — "
                f"модуль `{meta.get('module')}`, score `{item.score:.4f}`, source `{item.source}`"
            )
            st.code(item.document.page_content[:600])

        st.markdown("### 3. Скоринг")
        st.table(
            [
                {
                    "rank": index,
                    "file": item.document.metadata.get("file_name"),
                    "module": item.document.metadata.get("module"),
                    "score": round(item.score, 4),
                    "source": item.source,
                }
                for index, item in enumerate(result.retrieved_documents, start=1)
            ]
        )

        st.markdown("### 4. Финальный контекст")
        st.text_area("context", result.context, height=250)

        st.markdown("### 5. Ответ модели")
        st.markdown(result.answer)
