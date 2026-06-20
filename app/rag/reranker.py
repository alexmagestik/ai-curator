from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.documents import Document

from app.utils.config import Settings, get_settings


class BaseReranker(ABC):
    """Interface for document re-ranking after hybrid retrieval."""

    @abstractmethod
    def rerank(self, query: str, documents: list[Document], top_k: int) -> list[Document]:
        """Return documents sorted by relevance to the query."""


class NoOpReranker(BaseReranker):
    def rerank(self, query: str, documents: list[Document], top_k: int) -> list[Document]:
        return documents[:top_k]


class BGEReranker(BaseReranker):
    """Cross-encoder reranker (BAAI/bge-reranker-v2-m3)."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise ImportError(
                "Reranker dependencies are missing. Install them with:\n"
                "  pip install -r requirements-reranker.txt"
            ) from exc
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, documents: list[Document], top_k: int) -> list[Document]:
        if not documents:
            return []

        pairs = [(query, doc.page_content) for doc in documents]
        scores = self._model.predict(pairs)
        ranked = sorted(
            zip(documents, scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        return [doc for doc, _ in ranked[:top_k]]


def get_reranker(settings: Settings | None = None) -> BaseReranker:
    settings = settings or get_settings()
    if settings.use_reranker:
        return BGEReranker()
    return NoOpReranker()
