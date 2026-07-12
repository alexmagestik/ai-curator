from app.prompts.loader import build_system_prompt, load_fewshot_examples, load_system_prompt


def test_load_system_prompt_not_empty() -> None:
    assert "куратор" in load_system_prompt().lower()


def test_load_fewshot_examples_has_ten_items_each() -> None:
    examples = load_fewshot_examples()
    assert len(examples["correct"]) >= 10
    assert len(examples["incorrect"]) >= 10


def test_build_system_prompt_includes_level() -> None:
    prompt = build_system_prompt(user_level="beginner")
    assert "Beginner" in prompt
    assert "Примеры корректных ответов" in prompt


def test_build_system_prompt_uses_base_override() -> None:
    prompt = build_system_prompt(user_level="advanced", base_prompt="СВОЙ ПРОМПТ")
    assert prompt.startswith("СВОЙ ПРОМПТ")
    assert "Advanced" in prompt
    assert "Примеры корректных ответов" in prompt
    assert load_system_prompt() not in prompt
