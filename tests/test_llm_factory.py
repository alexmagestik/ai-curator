from app.services.llm_factory import get_llm
from app.utils.config import Settings


def test_get_llm_openai(settings: Settings) -> None:
    llm = get_llm(settings)
    model = getattr(llm, "model_name", None) or getattr(llm, "model", "")
    assert "gpt-4o-mini" in str(model)
