from __future__ import annotations

import gc
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.conversion.pipeline import ConversionResult, convert_knowledge_base
from app.conversion.validator import ValidationReport, validate_markdown_tree
from app.loaders.registry import scan_knowledge_base
from app.rag.chunker import split_documents
from app.utils.config import Settings, get_settings


@dataclass(frozen=True)
class IndexResult:
    source_files: int
    chunks_indexed: int
    collection_name: str
    vector_db_path: str
    files_converted: int = 0
    conversion_errors: int = 0
    validation_warnings: int = 0
    validation_failures: int = 0


def prepare_markdown(
    settings: Settings,
    force: bool = False,
) -> tuple[ConversionResult, ValidationReport]:
    """Convert sources to Markdown, then validate the Markdown tree.

    This is the first stage of indexing: ODT/PDF sources in
    ``knowledge_base/`` are converted into ``knowledge_base_md/`` and the
    resulting Markdown is validated before anything is added to ChromaDB.
    """
    conversion = convert_knowledge_base(
        settings.knowledge_base_path,
        settings.knowledge_base_md_path,
        settings.supported_extensions,
        force=force,
    )
    report = validate_markdown_tree(settings.knowledge_base_md_path)
    return conversion, report


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


def _ensure_vector_db_writable(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o777)
    except OSError:
        pass


def close_vector_store(vector_store: Chroma | None) -> None:
    """Release Chroma file handles so the persist directory can be updated."""
    if vector_store is None:
        return
    try:
        client = getattr(vector_store, "_client", None)
        if client is not None:
            reset = getattr(client, "reset", None)
            if callable(reset):
                reset()
    except Exception:
        pass
    finally:
        del vector_store
        gc.collect()


def _delete_chroma_collection(settings: Settings) -> None:
    if not settings.vector_db_path.exists():
        return
    client = None
    try:
        client = chromadb.PersistentClient(path=str(settings.vector_db_path))
        client.delete_collection(settings.collection_name)
    except Exception:
        pass
    finally:
        if client is not None:
            del client
        gc.collect()


def reset_vector_store(settings: Settings) -> None:
    """Drop persisted vectors, tolerating open handles from cached Streamlit resources."""
    _delete_chroma_collection(settings)
    path = settings.vector_db_path
    if not path.exists():
        return

    gc.collect()
    time.sleep(0.1)

    try:
        shutil.rmtree(path)
        return
    except OSError:
        stale = path.with_name(f"{path.name}.stale.{int(time.time())}")
        try:
            path.rename(stale)
        except OSError:
            return
        shutil.rmtree(stale, ignore_errors=True)


def load_index(settings: Settings | None = None) -> Chroma:
    settings = settings or get_settings()
    _ensure_vector_db_writable(settings.vector_db_path)
    return Chroma(
        collection_name=settings.collection_name,
        embedding_function=_get_embeddings(settings),
        persist_directory=str(settings.vector_db_path),
    )


def build_index(settings: Settings | None = None) -> IndexResult:
    """Convert sources to Markdown, validate, then index new/changed chunks."""
    settings = settings or get_settings()
    conversion, report = prepare_markdown(settings)
    loaded_documents = scan_knowledge_base(
        settings.knowledge_base_md_path,
        (settings.markdown_extension,),
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

    close_vector_store(vector_store)

    return IndexResult(
        source_files=len(loaded_documents),
        chunks_indexed=len(docs_to_add),
        collection_name=settings.collection_name,
        vector_db_path=str(settings.vector_db_path),
        files_converted=conversion.converted_count,
        conversion_errors=conversion.error_count,
        validation_warnings=report.warn_count,
        validation_failures=report.fail_count,
    )


def rebuild_index(settings: Settings | None = None) -> IndexResult:
    """Reconvert every source, validate, drop the vector store and rebuild."""
    settings = settings or get_settings()
    conversion, report = prepare_markdown(settings, force=True)

    reset_vector_store(settings)

    loaded_documents = scan_knowledge_base(
        settings.knowledge_base_md_path,
        (settings.markdown_extension,),
    )
    chunks = split_documents(loaded_documents, settings)
    vector_store = load_index(settings)

    if chunks:
        ids = [_chunk_id(chunk) for chunk in chunks]
        vector_store.add_documents(documents=chunks, ids=ids)

    close_vector_store(vector_store)

    return IndexResult(
        source_files=len(loaded_documents),
        chunks_indexed=len(chunks),
        collection_name=settings.collection_name,
        vector_db_path=str(settings.vector_db_path),
        files_converted=conversion.converted_count,
        conversion_errors=conversion.error_count,
        validation_warnings=report.warn_count,
        validation_failures=report.fail_count,
    )
