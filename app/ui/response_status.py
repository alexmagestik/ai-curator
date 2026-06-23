from __future__ import annotations

from dataclasses import dataclass

MANUAL_REVIEW_TRIGGERS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("оценк", "балл", "grade", "оценить работу"),
        "Запрос об оценке",
        "ИИ-куратор не выставляет оценки и не прогнозирует результаты.",
    ),
    (
        ("перенес", "перенести", "изменить распис", "продлить дедлайн", "отсроч"),
        "Изменение правил курса",
        "Куратор не может менять дедлайны и расписание — только сообщает актуальные данные.",
    ),
    (
        ("оплат", "стоимост", "вернуть деньги", "refund", "тариф"),
        "Вопрос об оплате",
        "Финансовые вопросы обрабатывает поддержка платформы, не ИИ-куратор.",
    ),
    (
        ("преподав", "куратор", "наставник", "человек", "оператор", "живой"),
        "Запрос живого специалиста",
        "Студент просит связаться с человеком — нужна эскалация.",
    ),
    (
        ("не работает платформ", "ошибка сайта", "не могу войти", "баг", "сломал"),
        "Техническая проблема",
        "Технические сбои платформы решает служба поддержки.",
    ),
)

DEFAULT_ESCALATION_HINT = (
    "Напишите куратору курса через LMS или в канал поддержки платформы. "
    "Укажите тему вопроса и скриншот диалога при необходимости."
)


@dataclass(frozen=True)
class ResponseStatus:
    kind: str
    title: str
    message: str
    escalation_hint: str | None = None


def detect_manual_review(question: str) -> tuple[str, str] | None:
    normalized = question.lower()
    for keywords, title, message in MANUAL_REVIEW_TRIGGERS:
        if any(keyword in normalized for keyword in keywords):
            return title, message
    return None


def build_response_status(
    *,
    question: str,
    answer_found: bool,
    response_type: str,
    sources_count: int,
    question_category: str,
) -> ResponseStatus:
    manual = detect_manual_review(question)
    if manual:
        title, message = manual
        return ResponseStatus(
            kind="escalate",
            title=title,
            message=message,
            escalation_hint=DEFAULT_ESCALATION_HINT,
        )

    if not answer_found:
        if response_type == "lms":
            return ResponseStatus(
                kind="warning",
                title="Данных LMS недостаточно",
                message=(
                    "В расписании и заданиях нет информации для точного ответа. "
                    "Проверьте данные в LMS или уточните формулировку."
                ),
                escalation_hint=DEFAULT_ESCALATION_HINT,
            )
        return ResponseStatus(
            kind="warning",
            title="Материалы курса не покрывают вопрос",
            message=(
                "В базе знаний не найдено достаточных фрагментов. "
                "Попробуйте указать модуль или переформулировать запрос."
            ),
            escalation_hint=DEFAULT_ESCALATION_HINT,
        )

    if response_type == "rag" and sources_count <= 1:
        return ResponseStatus(
            kind="info",
            title="Ответ по ограниченному числу источников",
            message=(
                "Ответ опирается на один фрагмент материалов. "
                "Для углубления откройте полный документ модуля."
            ),
        )

    if response_type == "lms" and question_category in {"deadline", "schedule", "assignment"}:
        return ResponseStatus(
            kind="success",
            title="Организационный ответ из LMS",
            message="Данные взяты из расписания и заданий курса.",
        )

    return ResponseStatus(
        kind="success",
        title="Ответ на основе материалов курса",
        message="Источники указаны ниже — проверьте модуль и документ.",
    )


def format_chat_error(exc: Exception) -> tuple[str, str]:
    message = str(exc).strip()
    lowered = message.lower()
    name = type(exc).__name__

    if "api_key" in lowered or "authentication" in lowered or "401" in lowered:
        return (
            "Ошибка авторизации OpenAI",
            "Проверьте `OPENAI_API_KEY` в файле `.env` и перезапустите приложение.",
        )
    if "rate limit" in lowered or "429" in lowered or "ratelimit" in name.lower():
        return (
            "Превышен лимит запросов к API",
            "Подождите 1–2 минуты и повторите вопрос. При частых обращениях проверьте квоту OpenAI.",
        )
    if "timeout" in lowered or "timed out" in lowered:
        return (
            "Превышено время ожидания ответа",
            "Сервис LLM не ответил вовремя. Повторите запрос или проверьте сеть.",
        )
    if "connection" in lowered or "network" in lowered or "connect" in name.lower():
        return (
            "Проблема с сетевым подключением",
            "Проверьте интернет и доступность OpenAI API.",
        )
    if "insufficient_quota" in lowered or "quota" in lowered:
        return (
            "Исчерпана квота OpenAI",
            "Пополните баланс аккаунта OpenAI или смените ключ в `.env`.",
        )

    short = message[:240] + ("…" if len(message) > 240 else "")
    return (
        "Не удалось получить ответ",
        f"{name}: {short}" if short else "Повторите запрос или обратитесь к администратору.",
    )


def render_status_banner(status: ResponseStatus) -> None:
    import streamlit as st

    if status.kind == "success":
        st.success(f"**{status.title}** — {status.message}")
    elif status.kind == "info":
        st.info(f"**{status.title}** — {status.message}")
    elif status.kind == "warning":
        st.warning(f"**{status.title}** — {status.message}")
    elif status.kind == "escalate":
        st.warning(f"**{status.title}** — {status.message}")
    else:
        st.info(f"**{status.title}** — {status.message}")

    if status.escalation_hint:
        st.caption(f"Рекомендация: {status.escalation_hint}")
