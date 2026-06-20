from __future__ import annotations

from langchain_core.documents import Document

from app.rag.retriever import (
    _build_chroma_filter,
    _matches_filters,
    _merge_results,
)


def test_build_chroma_filter_single_key() -> None:
    assert _build_chroma_filter({"module": "module_01"}) == {"module": "module_01"}


def test_build_chroma_filter_multiple_keys() -> None:
    result = _build_chroma_filter({"module": "module_01", "resource_type": "lecture"})
    assert result == {
        "$and": [
            {"module": "module_01"},
            {"resource_type": "lecture"},
        ]
    }


def test_matches_filters() -> None:
    doc = Document(
        page_content="text",
        metadata={"module": "module_01", "resource_type": "lecture"},
    )
    assert _matches_filters(doc, {"module": "module_01"})
    assert not _matches_filters(doc, {"module": "module_02"})


def test_merge_results_deduplicates_documents() -> None:
    doc = Document(
        page_content="Python backend",
        metadata={"source_path": "/tmp/a.odt", "chunk_index": "0"},
    )
    merged = _merge_results(
        [doc],
        [doc],
        bm25_weight=0.5,
        vector_weight=0.5,
        top_k=5,
    )
    assert len(merged) == 1
    assert merged[0].source == "hybrid"
    assert merged[0].score > 0
