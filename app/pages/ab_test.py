"""A/B testing page for comparing system prompts (admin).

Blind evaluation: after each question the two answers (prompt A = current,
prompt B = custom) are placed left/right at random. The evaluator marks each
answer with Relevance / Hallucination checkboxes without knowing which variant
is which. Results are mapped back to the real variant and aggregated per session.
"""

from __future__ import annotations

import random

import streamlit as st

from app.auth.session import is_admin
from app.prompts.loader import load_system_prompt
from app.rag.pipeline import RAGPipeline, USER_LEVELS
from app.utils.config import get_settings

_PROMPT_HEIGHT = 320
_MAX_QUESTIONS = 30
_QUESTION_PREVIEW = 70

_SYMBOL_CORRECT = "✅"
_SYMBOL_IRRELEVANT = "❌"
_SYMBOL_HALLUCINATION = "👻"

_SIDES = ("left", "right")
_SIDE_TITLES = {"left": "Ответ слева", "right": "Ответ справа"}


@st.cache_resource
def get_ab_pipeline() -> RAGPipeline:
    return RAGPipeline()


def _result_symbol(relevant: bool, hallucinated: bool) -> str:
    if hallucinated:
        return _SYMBOL_HALLUCINATION
    return _SYMBOL_CORRECT if relevant else _SYMBOL_IRRELEVANT


def _init_eval_state() -> None:
    for side in _SIDES:
        st.session_state.setdefault(f"ab_eval_{side}_relevant", True)
        st.session_state.setdefault(f"ab_eval_{side}_relevant_prev", True)
        st.session_state.setdefault(f"ab_eval_{side}_halluc", False)


def _reset_eval_state() -> None:
    for side in _SIDES:
        st.session_state[f"ab_eval_{side}_relevant"] = True
        st.session_state[f"ab_eval_{side}_relevant_prev"] = True
        st.session_state[f"ab_eval_{side}_halluc"] = False


def _on_halluc_change(side: str) -> None:
    halluc_key = f"ab_eval_{side}_halluc"
    rel_key = f"ab_eval_{side}_relevant"
    prev_key = f"ab_eval_{side}_relevant_prev"
    if st.session_state[halluc_key]:
        st.session_state[prev_key] = st.session_state.get(rel_key, True)
        st.session_state[rel_key] = False
    else:
        st.session_state[rel_key] = st.session_state.get(prev_key, True)


def _on_evaluate() -> None:
    current = st.session_state.get("ab_current")
    if not current:
        return

    positions = current["positions"]
    record = {"question": current["question"]}
    for side in _SIDES:
        halluc = bool(st.session_state.get(f"ab_eval_{side}_halluc", False))
        relevant = bool(st.session_state.get(f"ab_eval_{side}_relevant", True)) and not halluc
        variant = positions[side]
        record[f"{variant}_relevant"] = relevant
        record[f"{variant}_halluc"] = halluc

    st.session_state.setdefault("ab_results", []).append(record)
    st.session_state["ab_current"] = None
    st.session_state["ab_question"] = ""
    _reset_eval_state()


def _on_skip() -> None:
    st.session_state["ab_current"] = None
    st.session_state["ab_question"] = ""
    _reset_eval_state()


def _on_reset_session() -> None:
    st.session_state["ab_results"] = []
    st.session_state["ab_current"] = None
    st.session_state["ab_question"] = ""
    _reset_eval_state()


def _variant_stats(results: list[dict], variant: str) -> tuple[float, int, int]:
    total = len(results)
    correct = sum(1 for row in results if row.get(f"{variant}_relevant"))
    hallucinations = sum(1 for row in results if row.get(f"{variant}_halluc"))
    relevance = correct / total if total else 0.0
    return relevance, hallucinations, correct


def _render_prompt_inputs(current_prompt: str) -> str:
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### Вариант A — текущий системный промпт")
        st.text_area(
            "Текущий системный промпт (только чтение)",
            value=current_prompt,
            height=_PROMPT_HEIGHT,
            disabled=True,
            key="ab_prompt_current",
            label_visibility="collapsed",
        )
    with col_right:
        st.markdown("#### Вариант B — произвольный системный промпт")
        custom_prompt = st.text_area(
            "Произвольный системный промпт",
            value=st.session_state.get("ab_prompt_custom", current_prompt),
            height=_PROMPT_HEIGHT,
            key="ab_prompt_custom",
            label_visibility="collapsed",
        )
    st.caption(
        "К обоим вариантам одинаково добавляются инструкции по уровню студента "
        "и few-shot примеры — сравниваются именно базовые промпты."
    )
    return custom_prompt


def _render_evaluation(current: dict) -> None:
    _init_eval_state()

    st.divider()
    st.subheader("Оцените ответы")
    st.caption(
        "Ответы размещены случайно, вариант промпта скрыт. "
        "Relevance — ответ корректен (по умолчанию да). "
        "Hallucinations — модель выдумывает (при включении Relevance снимается)."
    )

    answers = current["answers"]
    positions = current["positions"]
    columns = st.columns(2)

    for column, side in zip(columns, _SIDES):
        with column:
            st.markdown(f"#### {_SIDE_TITLES[side]}")
            with st.container(border=True):
                st.markdown(answers[positions[side]] or "_Пустой ответ._")

            halluc_key = f"ab_eval_{side}_halluc"
            st.checkbox(
                "Relevance — ответ корректен",
                key=f"ab_eval_{side}_relevant",
                disabled=st.session_state.get(halluc_key, False),
            )
            st.checkbox(
                "Hallucinations — модель галлюцинирует",
                key=halluc_key,
                on_change=_on_halluc_change,
                args=(side,),
            )

    st.button("Оценить", type="primary", on_click=_on_evaluate, use_container_width=True)

    with st.expander("Общий контекст (одинаков для обоих вариантов)"):
        docs = current.get("docs") or []
        if docs:
            st.table(docs)
        else:
            st.info("Документы не найдены — обе модели отвечали без контекста.")
        st.text_area(
            "context",
            current.get("context", ""),
            height=220,
            disabled=True,
            key="ab_context_view",
        )


def _render_metrics_and_history() -> None:
    results = st.session_state.get("ab_results", [])
    total = len(results)

    st.divider()
    st.subheader("Метрики A/B сессии")
    st.caption(f"Оценено вопросов: {total} / {_MAX_QUESTIONS}")

    relevance_a, halluc_a, _ = _variant_stats(results, "A")
    relevance_b, halluc_b, _ = _variant_stats(results, "B")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Relevance A", f"{relevance_a:.0%}")
    m2.metric("Hallucinations A", halluc_a)
    m3.metric("Relevance B", f"{relevance_b:.0%}")
    m4.metric("Hallucinations B", halluc_b)
    if relevance_a > 0:
        lift = (relevance_b - relevance_a) / relevance_a * 100
        m5.metric("Relative Lift (B vs A)", f"{lift:+.0f}%")
    else:
        m5.metric("Relative Lift (B vs A)", "—")

    if not results:
        st.info("История пуста. Задайте вопрос, оцените ответы — строка добавится в таблицу.")
        return

    st.markdown("#### История ответов")
    st.dataframe(
        [
            {
                "Вопрос": _preview(row["question"]),
                "Модель A": _result_symbol(row.get("A_relevant", False), row.get("A_halluc", False)),
                "Модель B": _result_symbol(row.get("B_relevant", False), row.get("B_halluc", False)),
            }
            for row in results
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        f"{_SYMBOL_CORRECT} корректный · {_SYMBOL_IRRELEVANT} нерелевантный · "
        f"{_SYMBOL_HALLUCINATION} галлюцинация"
    )


def _preview(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= _QUESTION_PREVIEW:
        return text
    return text[:_QUESTION_PREVIEW].rstrip() + "…"


def render_ab_test_page() -> None:
    if not is_admin():
        st.error("Доступ только для администратора.")
        return

    settings = get_settings()
    st.title("A/B тесты")
    st.caption(
        "Слепое сравнение системных промптов при одинаковых параметрах: retrieval, "
        "контекст, уровень и модель идентичны — меняется только системный промпт."
    )

    if not settings.openai_api_key:
        st.error("Укажите OPENAI_API_KEY в `.env`.")
        return

    pipeline = get_ab_pipeline()
    current_prompt = load_system_prompt()

    custom_prompt = _render_prompt_inputs(current_prompt)

    st.divider()
    question = st.text_area(
        "Пользовательский промпт (вопрос)",
        placeholder="Что такое RAG и зачем он нужен?",
        key="ab_question",
    )

    param_col1, param_col2 = st.columns(2)
    with param_col1:
        user_level = st.selectbox(
            "Уровень студента",
            options=list(USER_LEVELS),
            index=1,
            format_func=lambda value: value.capitalize(),
            key="ab_user_level",
        )
    with param_col2:
        modules = ["Все модули", *pipeline.retriever.available_modules]
        selected_module = st.selectbox("Фильтр по модулю", options=modules, key="ab_module")

    total = len(st.session_state.get("ab_results", []))

    run_col, skip_col, reset_col = st.columns([2, 1, 1])
    with run_col:
        run_clicked = st.button(
            "Сравнить ответы",
            type="primary",
            use_container_width=True,
            disabled=total >= _MAX_QUESTIONS,
        )
    with skip_col:
        st.button(
            "Пропустить вопрос",
            on_click=_on_skip,
            use_container_width=True,
            disabled=not st.session_state.get("ab_current"),
        )
    with reset_col:
        st.button(
            "Сбросить сессию",
            on_click=_on_reset_session,
            use_container_width=True,
            disabled=total == 0 and not st.session_state.get("ab_current"),
        )

    if total >= _MAX_QUESTIONS:
        st.warning(f"Достигнут лимит {_MAX_QUESTIONS} вопросов. Сбросьте сессию, чтобы начать заново.")

    if run_clicked:
        if not question.strip():
            st.warning("Введите вопрос.")
        elif not custom_prompt.strip():
            st.warning("Промпт варианта B не может быть пустым.")
        else:
            filters: dict[str, str] = {}
            if selected_module != "Все модули":
                filters["module"] = selected_module

            with st.spinner("Отправляю оба запроса в модель..."):
                response_a, response_b = pipeline.compare_prompts(
                    question.strip(),
                    current_prompt,
                    custom_prompt,
                    user_level=user_level,
                    filters=filters or None,
                )

            positions = (
                {"left": "A", "right": "B"}
                if random.choice([True, False])
                else {"left": "B", "right": "A"}
            )
            st.session_state["ab_current"] = {
                "question": question.strip(),
                "answers": {"A": response_a.answer, "B": response_b.answer},
                "positions": positions,
                "context": response_a.context,
                "docs": [
                    {
                        "rank": index,
                        "file": item.document.metadata.get("file_name"),
                        "module": item.document.metadata.get("module"),
                        "score": round(item.score, 4),
                        "source": item.source,
                    }
                    for index, item in enumerate(response_a.retrieved_documents, start=1)
                ],
            }
            _reset_eval_state()

    current = st.session_state.get("ab_current")
    if current:
        _render_evaluation(current)

    _render_metrics_and_history()
