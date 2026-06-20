from __future__ import annotations

from langchain_core.documents import Document

from app.rag.context import build_context, extract_sources, format_sources_for_display
from app.rag.retriever import RetrievedDocument


def test_build_context_includes_module_and_document() -> None:
    doc = RetrievedDocument(
        document=Document(
            page_content="REST API basics",
            metadata={
                "module": "module_02",
                "file_name": "lecture_02.odt",
                "resource_type": "lecture",
            },
        ),
        score=1.0,
        source="vector",
    )
    context = build_context([doc])
    assert "module_02" in context
    assert "lecture_02.odt" in context
    assert "REST API basics" in context


def test_extract_sources_deduplicates_by_module_and_file() -> None:
    docs = [
        RetrievedDocument(
            document=Document(
                page_content="chunk 1",
                metadata={
                    "module": "module_01",
                    "file_name": "lecture_01.odt",
                    "resource_type": "lecture",
                },
            ),
            score=1.0,
            source="vector",
        ),
        RetrievedDocument(
            document=Document(
                page_content="chunk 2",
                metadata={
                    "module": "module_01",
                    "file_name": "lecture_01.odt",
                    "resource_type": "lecture",
                },
            ),
            score=0.8,
            source="bm25",
        ),
    ]
    sources = extract_sources(docs)
    assert len(sources) == 1
    assert sources[0].file_name == "lecture_01.odt"


def test_format_sources_for_display() -> None:
    sources = extract_sources(
        [
            RetrievedDocument(
                document=Document(
                    page_content="text",
                    metadata={
                        "module": "module_03",
                        "file_name": "lecture_01.odt",
                        "resource_type": "lecture",
                    },
                ),
                score=1.0,
                source="vector",
            )
        ]
    )
    rendered = format_sources_for_display(sources)
    assert "lecture_01.odt" in rendered
    assert "module_03" in rendered
