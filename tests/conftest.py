from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.utils.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    lms_data = tmp_path / "lms_data"
    lms_data.mkdir()
    (lms_data / "schedule.json").write_text('[{"module":"Python","lesson_date":"2026-07-01"}]', encoding="utf-8")
    (lms_data / "assignments.json").write_text('[{"title":"HW1","deadline":"2026-07-10"}]', encoding="utf-8")
    (lms_data / "course_info.json").write_text('{"course":"Python Backend"}', encoding="utf-8")

    return Settings(
        openai_api_key="test-key",
        openai_model="gpt-4o-mini",
        llm_provider="openai",
        vector_db_path=tmp_path / "vector_store",
        knowledge_base_path=tmp_path / "knowledge_base",
        chunk_size=1200,
        chunk_overlap=200,
        use_reranker=False,
        collection_name="test_collection",
        embedding_model="text-embedding-3-small",
        supported_extensions=(".odt",),
        top_k=5,
        bm25_weight=0.5,
        vector_weight=0.5,
        database_path=tmp_path / "app.db",
        max_history_messages=10,
        lms_api_url="http://127.0.0.1:8000",
        lms_data_path=tmp_path / "lms_data",
    )
