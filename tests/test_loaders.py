from __future__ import annotations

from pathlib import Path

import pytest
from odf.opendocument import OpenDocumentText
from odf.text import P

from app.loaders.odt_loader import ODTLoader
from app.loaders.registry import scan_knowledge_base
from app.rag.chunker import split_documents
from app.utils.config import Settings
from app.utils.text_utils import clean_text, infer_resource_type


@pytest.fixture
def sample_odt(tmp_path: Path) -> Path:
    file_path = tmp_path / "module_01" / "lecture_01.odt"
    file_path.parent.mkdir(parents=True)
    document = OpenDocumentText()
    document.text.addElement(
        P(text="Python Backend course introduction and virtual environments.")
    )
    document.text.addElement(P(text="Students learn REST API and databases."))
    document.save(str(file_path))
    return file_path


def test_clean_text_normalizes_whitespace() -> None:
    assert clean_text("hello   world\n\n\n\nnext") == "hello world\n\nnext"


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("lecture_01.odt", "lecture"),
        ("faq.odt", "faq"),
        ("notes.odt", "document"),
    ],
)
def test_infer_resource_type(file_name: str, expected: str) -> None:
    assert infer_resource_type(file_name) == expected


def test_odt_loader_extracts_text_and_metadata(sample_odt: Path) -> None:
    loader = ODTLoader()
    loaded = loader.load(sample_odt, module="module_01")

    assert "Python Backend" in loaded.text
    assert loaded.metadata["module"] == "module_01"
    assert loaded.metadata["file_name"] == "lecture_01.odt"
    assert loaded.metadata["resource_type"] == "lecture"
    assert loaded.metadata["topic"] == "lecture_01"
    assert loaded.metadata["source_path"] == str(sample_odt.resolve())
    assert "last_modified" in loaded.metadata


def test_scan_knowledge_base_finds_odt_files(sample_odt: Path) -> None:
    documents = scan_knowledge_base(sample_odt.parent.parent, (".odt",))
    assert len(documents) == 1
    assert documents[0].metadata["module"] == "module_01"


def test_split_documents_respects_chunk_size(sample_odt: Path) -> None:
    loader = ODTLoader()
    loaded = loader.load(sample_odt, module="module_01")
    settings = Settings(
        openai_api_key="test",
        openai_model="gpt-4o-mini",
        llm_provider="openai",
        vector_db_path=Path("/tmp/vector_store"),
        knowledge_base_path=Path("/tmp/knowledge_base"),
        knowledge_base_md_path=Path("/tmp/knowledge_base_md"),
        chunk_size=40,
        chunk_overlap=10,
        use_reranker=False,
        collection_name="test",
        embedding_model="text-embedding-3-small",
        supported_extensions=(".odt", ".pdf"),
        markdown_extension=".md",
        top_k=5,
        bm25_weight=0.5,
        vector_weight=0.5,
        database_path=Path("/tmp/app.db"),
        max_history_messages=10,
        lms_api_url="http://127.0.0.1:8000",
        lms_data_path=Path("/tmp/lms_data"),
    )

    chunks = split_documents([loaded], settings)
    assert chunks
    assert all(chunk.metadata["module"] == "module_01" for chunk in chunks)
    assert all(len(chunk.page_content) <= 40 for chunk in chunks)
