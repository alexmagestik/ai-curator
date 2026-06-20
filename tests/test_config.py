from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.utils.config import get_settings


def test_get_settings_reads_env_and_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {
                "knowledge_base": {"path": "./custom_kb", "supported_extensions": [".odt"]},
                "indexing": {"collection_name": "custom_collection", "chunk_size": 900},
                "vector_store": {"path": "./custom_vs"},
                "embeddings": {"model": "text-embedding-3-large"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("CHUNK_OVERLAP", "100")
    get_settings.cache_clear()

    settings = get_settings(config_path=config_path)
    assert settings.openai_api_key == "secret"
    assert settings.chunk_size == 900
    assert settings.chunk_overlap == 100
    assert settings.collection_name == "custom_collection"
    assert settings.embedding_model == "text-embedding-3-large"
    assert settings.supported_extensions == (".odt",)

    get_settings.cache_clear()
