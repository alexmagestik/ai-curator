from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.rag.indexer import (
    IndexResult,
    build_index,
    clear_vector_collection,
    rebuild_index,
    reset_vector_store,
)
from app.utils.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        openai_api_key="test-key",
        openai_model="gpt-4o-mini",
        llm_provider="openai",
        vector_db_path=tmp_path / "vector_store",
        knowledge_base_path=tmp_path / "knowledge_base",
        knowledge_base_md_path=tmp_path / "knowledge_base_md",
        chunk_size=1200,
        chunk_overlap=200,
        use_reranker=False,
        collection_name="test_collection",
        embedding_model="text-embedding-3-small",
        supported_extensions=(".odt", ".pdf"),
        markdown_extension=".md",
        top_k=5,
        bm25_weight=0.5,
        vector_weight=0.5,
        database_path=tmp_path / "app.db",
        max_history_messages=10,
        lms_api_url="http://127.0.0.1:8000",
        lms_data_path=tmp_path / "lms_data",
    )


def test_build_index_skips_existing_chunks(settings: Settings) -> None:
    mock_store = MagicMock()
    mock_store.get.return_value = {"ids": ["doc::0::2026-01-01"]}

    with (
        patch("app.rag.indexer.scan_knowledge_base", return_value=[]),
        patch("app.rag.indexer.split_documents", return_value=[]),
        patch("app.rag.indexer.load_index", return_value=mock_store),
    ):
        result = build_index(settings)

    assert result == IndexResult(
        source_files=0,
        chunks_indexed=0,
        collection_name="test_collection",
        vector_db_path=str(settings.vector_db_path),
    )
    mock_store.add_documents.assert_not_called()


def test_rebuild_index_clears_store_and_indexes(settings: Settings) -> None:
    mock_store = MagicMock()
    chunk = MagicMock()
    chunk.metadata = {
        "source_path": "/tmp/file.odt",
        "chunk_index": 0,
        "last_modified": "2026-01-01",
    }

    with (
        patch("app.rag.indexer.scan_knowledge_base", return_value=[]),
        patch("app.rag.indexer.split_documents", return_value=[chunk]),
        patch("app.rag.indexer.clear_vector_collection") as mock_clear,
        patch("app.rag.indexer.load_index", return_value=mock_store),
    ):
        result = rebuild_index(settings)

    mock_clear.assert_called_once_with(settings)
    assert result.chunks_indexed == 1
    mock_store.add_documents.assert_called_once()


def test_clear_vector_collection_keeps_persist_directory(settings: Settings) -> None:
    settings.vector_db_path.mkdir(parents=True)
    (settings.vector_db_path / "chroma.sqlite3").write_text("db", encoding="utf-8")

    mock_client = MagicMock()
    with (
        patch("app.rag.indexer.load_index", side_effect=RuntimeError("no collection")),
        patch("app.rag.indexer.chromadb.PersistentClient", return_value=mock_client),
    ):
        clear_vector_collection(settings)

    assert settings.vector_db_path.exists()
    mock_client.delete_collection.assert_called_once_with("test_collection")


def test_reset_vector_store_delegates_to_clear(settings: Settings) -> None:
    with patch("app.rag.indexer.clear_vector_collection") as mock_clear:
        reset_vector_store(settings)
    mock_clear.assert_called_once_with(settings)
