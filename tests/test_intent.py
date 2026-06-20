from app.services.level_detector import classify_intent


def test_classify_intent_organizational() -> None:
    assert classify_intent("Когда дедлайн домашней работы?") == "organizational"
    assert classify_intent("Когда следующее занятие?") == "organizational"
    assert classify_intent("Какие задания мне нужно выполнить?") == "organizational"


def test_classify_intent_knowledge() -> None:
    assert classify_intent("Что такое виртуальное окружение?") == "knowledge"
    assert classify_intent("Объясни REST API") == "knowledge"
