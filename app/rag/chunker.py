from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.loaders.base import LoadedDocument
from app.utils.config import Settings


def split_documents(
    loaded_documents: list[LoadedDocument],
    settings: Settings,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )

    documents: list[Document] = []
    for loaded in loaded_documents:
        if not loaded.text.strip():
            continue
        chunks = splitter.split_text(loaded.text)
        for index, chunk in enumerate(chunks):
            metadata = {
                **loaded.metadata,
                "chunk_index": str(index),
                "chunk_total": str(len(chunks)),
            }
            documents.append(Document(page_content=chunk, metadata=metadata))
    return documents
