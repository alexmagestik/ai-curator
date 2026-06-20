from __future__ import annotations

import shutil
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.loaders.registry import scan_knowledge_base
from app.rag.chunker import split_documents
from app.utils.config import Settings, get_settings


@dataclass(frozen=True)
class IndexResult:
    source_files: int
    chunks_indexed: int
    collection_name: str
    vector_db_path: str


def _get_embeddings(settings: Settings) -> OpenAIEmbeddings:
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to .env before indexing documents."
        )
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
    )


def _chunk_id(document: Document) -> str:
    metadata = document.metadata
    return (
        f"{metadata['source_path']}::"
        f"{metadata.get('chunk_index', 0)}::"
        f"{metadata.get('last_modified', '')}"
    )


def load_index(settings: Settings | None = None) -> Chroma:
    settings = settings or get_settings()
    settings.vector_db_path.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=settings.collection_name,
        embedding_function=_get_embeddings(settings),
        persist_directory=str(settings.vector_db_path),
    )


def build_index(settings: Settings | None = None) -> IndexResult:
    """Index new or changed documents into ChromaDB."""
    settings = settings or get_settings()
    loaded_documents = scan_knowledge_base(
        settings.knowledge_base_path,
        settings.supported_extensions,
    )
    chunks = split_documents(loaded_documents, settings)

    vector_store = load_index(settings)
    store_data = vector_store.get()
    existing_ids = set(store_data.get("ids") or [])
    ids_to_add: list[str] = []
    docs_to_add: list[Document] = []

    for chunk in chunks:
        chunk_id = _chunk_id(chunk)
        if chunk_id in existing_ids:
            continue
        ids_to_add.append(chunk_id)
        docs_to_add.append(chunk)

    if docs_to_add:
        vector_store.add_documents(documents=docs_to_add, ids=ids_to_add)

    return IndexResult(
        source_files=len(loaded_documents),
        chunks_indexed=len(docs_to_add),
        collection_name=settings.collection_name,
        vector_db_path=str(settings.vector_db_path),
    )


def rebuild_index(settings: Settings | None = None) -> IndexResult:
    """Remove existing vector store and rebuild from scratch."""
    settings = settings or get_settings()
    if settings.vector_db_path.exists():
        shutil.rmtree(settings.vector_db_path)

    loaded_documents = scan_knowledge_base(
        settings.knowledge_base_path,
        settings.supported_extensions,
    )
    chunks = split_documents(loaded_documents, settings)
    vector_store = load_index(settings)

    if chunks:
        ids = [_chunk_id(chunk) for chunk in chunks]
        vector_store.add_documents(documents=chunks, ids=ids)

    return IndexResult(
        source_files=len(loaded_documents),
        chunks_indexed=len(chunks),
        collection_name=settings.collection_name,
        vector_db_path=str(settings.vector_db_path),
    )
