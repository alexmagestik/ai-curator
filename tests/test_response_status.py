from __future__ import annotations

from app.ui.response_status import build_response_status, detect_manual_review, format_chat_error


def test_detect_manual_review_grade() -> None:
    result = detect_manual_review("Какую оценку я получу за проект?")
    assert result is not None
    assert "оценк" in result[0].lower() or "оцен" in result[1].lower()


def test_build_response_status_escalate_on_grade() -> None:
    status = build_response_status(
        question="Поставь мне оценку за домашку",
        answer_found=True,
        response_type="rag",
        sources_count=3,
        question_category="course_content",
    )
    assert status.kind == "escalate"
    assert status.escalation_hint is not None


def test_build_response_status_no_rag_sources() -> None:
    status = build_response_status(
        question="Что такое Kubernetes?",
        answer_found=False,
        response_type="rag",
        sources_count=0,
        question_category="course_content",
    )
    assert status.kind == "warning"
    assert status.escalation_hint is not None


def test_build_response_status_lms_success() -> None:
    status = build_response_status(
        question="Когда дедлайн?",
        answer_found=True,
        response_type="lms",
        sources_count=0,
        question_category="deadline",
    )
    assert status.kind == "success"


def test_format_chat_error_rate_limit() -> None:
    title, hint = format_chat_error(Exception("Rate limit exceeded"))
    assert "лимит" in title.lower()
    assert hint


def test_format_chat_error_generic() -> None:
    title, hint = format_chat_error(RuntimeError("unexpected"))
    assert title
    assert hint
