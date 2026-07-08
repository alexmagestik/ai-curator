"""Knowledge base overview and reindexing (admin)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.auth.session import is_admin
from app.loaders.registry import scan_knowledge_base
from app.rag.indexer import build_index, rebuild_index
from app.utils.config import get_settings


def _scan_modules(md_path: Path) -> dict[str, list[str]]:
    documents = scan_knowledge_base(
        md_path,
        (get_settings().markdown_extension,),
    )
    modules: dict[str, list[str]] = {}
    for doc in documents:
        module = doc.metadata.get("module", "unknown")
        file_name = doc.metadata.get("file_name", "unknown")
        modules.setdefault(module, []).append(file_name)
    return modules


def render_knowledge_base_page() -> None:
    if not is_admin():
        st.error("Доступ только для администратора.")
        return

    settings = get_settings()
    st.title("База знаний")
    st.caption(
        "Конвертированные Markdown-документы (knowledge_base_md/), "
        "статистика по модулям и переиндексация."
    )

    modules = _scan_modules(settings.knowledge_base_md_path)
    if not modules:
        st.warning(
            "Markdown-документы не найдены в `knowledge_base_md/`. "
            "Запустите индексацию, чтобы сконвертировать исходники."
        )
    else:
        total_docs = sum(len(files) for files in modules.values())
        st.metric("Всего документов", total_docs)
        st.metric("Модулей", len(modules))

        for module, files in sorted(modules.items()):
            with st.expander(f"{module} ({len(files)} файлов)"):
                for file_name in sorted(set(files)):
                    st.write(f"- {file_name}")

    st.divider()
    st.subheader("Переиндексация")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Инкрементальная индексация", use_container_width=True):
            with st.spinner("Индексация..."):
                result = build_index(settings)
            st.success(
                f"Просканировано файлов: {result.source_files}. "
                f"Новых чанков: {result.chunks_indexed}."
            )
    with col2:
        if st.button("Полная переиндексация", type="primary", use_container_width=True):
            with st.spinner("Переиндексация..."):
                result = rebuild_index(settings)
            st.success(
                f"Проиндексировано файлов: {result.source_files}. "
                f"Чанков: {result.chunks_indexed}."
            )
            st.cache_resource.clear()
