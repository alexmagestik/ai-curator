from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from app.services.level_detector import LevelDetector


def test_level_detector_parses_json_response() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"level": "advanced", "confidence": 0.91}'
    )

    detector = LevelDetector(llm=mock_llm)
    result = detector.detect("Explain SQLAlchemy session lifecycle in detail")

    assert result.level == "advanced"
    assert result.confidence == 0.91


def test_level_detector_fallback_on_invalid_json() -> None:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="not json")

    detector = LevelDetector(llm=mock_llm)
    result = detector.detect("hello")

    assert result.level == "intermediate"
    assert result.confidence == 0.5
