from app.analytics.categories import categorize_question, detect_answer_found


def test_categorize_question_course_content() -> None:
    assert categorize_question("Что такое REST API?") == "course_content"


def test_categorize_question_deadline() -> None:
    assert categorize_question("Когда дедлайн домашней работы?") == "deadline"


def test_categorize_question_schedule() -> None:
    assert categorize_question("Когда следующее занятие?") == "schedule"


def test_detect_answer_found_rag() -> None:
    assert detect_answer_found("Python — язык программирования.", 2, "rag")
    assert not detect_answer_found("Недостаточно данных в контексте.", 0, "rag")


def test_detect_answer_found_lms() -> None:
    assert detect_answer_found("Дедлайн 10 июля.", 0, "lms")
    assert not detect_answer_found("Нет данных о дедлайне.", 0, "lms")
