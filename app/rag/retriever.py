from __future__ import annotations

from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from app.rag.indexer import load_index
from app.rag.reranker import BaseReranker, get_reranker
from app.utils.config import Settings, get_settings

FILTER_KEYS = ("module", "topic", "resource_type", "file_name")


@dataclass(frozen=True)
class RetrievedDocument:
    document: Document
    score: float
    source: str


def _document_key(document: Document) -> str:
    metadata = document.metadata
    return (
        f"{metadata.get('source_path', '')}::"
        f"{metadata.get('chunk_index', '')}"
    )


def _build_chroma_filter(filters: dict[str, str]) -> dict:
    if not filters:
        return {}
    if len(filters) == 1:
        key, value = next(iter(filters.items()))
        return {key: value}
    return {"$and": [{key: value} for key, value in filters.items()]}


def _matches_filters(document: Document, filters: dict[str, str]) -> bool:
    if not filters:
        return True
    metadata = document.metadata
    return all(metadata.get(key) == value for key, value in filters.items())


def _load_all_documents(vector_store: Chroma) -> list[Document]:
    data = vector_store.get(include=["documents", "metadatas"])
    documents: list[Document] = []
    for content, metadata in zip(
        data.get("documents") or [],
        data.get("metadatas") or [],
        strict=True,
    ):
        documents.append(Document(page_content=content, metadata=metadata))
    return documents


def _merge_results(
    vector_docs: list[Document],
    bm25_docs: list[Document],
    *,
    bm25_weight: float,
    vector_weight: float,
    top_k: int,
) -> list[RetrievedDocument]:
    scores: dict[str, float] = {}
    sources: dict[str, str] = {}
    documents: dict[str, Document] = {}

    for rank, doc in enumerate(vector_docs):
        key = _document_key(doc)
        documents[key] = doc
        sources[key] = "vector"
        scores[key] = scores.get(key, 0.0) + vector_weight / (rank + 1)

    for rank, doc in enumerate(bm25_docs):
        key = _document_key(doc)
        documents[key] = doc
        sources[key] = "hybrid" if key in sources else "bm25"
        scores[key] = scores.get(key, 0.0) + bm25_weight / (rank + 1)

    ranked_keys = sorted(scores, key=scores.get, reverse=True)[:top_k]
    return [
        RetrievedDocument(
            document=documents[key],
            score=scores[key],
            source=sources[key],
        )
        for key in ranked_keys
    ]


class HybridRetriever:
    """Hybrid BM25 + vector search with optional metadata filtering."""

    def __init__(
        self,
        settings: Settings | None = None,
        reranker: BaseReranker | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.reranker = reranker or get_reranker(self.settings)
        self._vector_store = load_index(self.settings)
        self._all_documents = _load_all_documents(self._vector_store)

    @property
    def available_modules(self) -> list[str]:
        modules = {
            doc.metadata.get("module", "")
            for doc in self._all_documents
            if doc.metadata.get("module")
        }
        return sorted(modules)

    def search(
        self,
        query: str,
        *,
        filters: dict[str, str] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedDocument]:
        filters = filters or {}
        top_k = top_k or self.settings.top_k
        fetch_k = top_k * 2

        chroma_filter = _build_chroma_filter(filters)
        search_kwargs: dict = {"k": fetch_k}
        if chroma_filter:
            search_kwargs["filter"] = chroma_filter

        vector_docs = self._vector_store.similarity_search(query, **search_kwargs)

        corpus = [
            doc for doc in self._all_documents if _matches_filters(doc, filters)
        ]
        bm25_docs: list[Document] = []
        if corpus:
            bm25 = BM25Retriever.from_documents(corpus)
            bm25.k = fetch_k
            bm25_docs = bm25.invoke(query)

        merged = _merge_results(
            vector_docs,
            bm25_docs,
            bm25_weight=self.settings.bm25_weight,
            vector_weight=self.settings.vector_weight,
            top_k=fetch_k,
        )

        documents = [item.document for item in merged]
        reranked = self.reranker.rerank(query, documents, top_k=top_k)

        reranked_keys = [_document_key(doc) for doc in reranked]
        score_map = {_document_key(item.document): item.score for item in merged}
        source_map = {_document_key(item.document): item.source for item in merged}

        return [
            RetrievedDocument(
                document=doc,
                score=score_map.get(_document_key(doc), 0.0),
                source=source_map.get(_document_key(doc), "reranked"),
            )
            for doc in reranked
        ]
