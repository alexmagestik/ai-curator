from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document

from app.rag.retriever import RetrievedDocument


@dataclass(frozen=True)
class SourceReference:
    file_name: str
    module: str
    resource_type: str
    excerpt: str


def build_context(documents: list[RetrievedDocument]) -> str:
    """Format retrieved fragments for the LLM prompt."""
    if not documents:
        return "Релевантные материалы не найдены."

    blocks: list[str] = []
    for index, item in enumerate(documents, start=1):
        metadata = item.document.metadata
        blocks.append(
            f"[Источник {index}]\n"
            f"Модуль: {metadata.get('module', 'неизвестно')}\n"
            f"Документ: {metadata.get('file_name', 'неизвестно')}\n"
            f"Тип: {metadata.get('resource_type', 'document')}\n"
            f"Фрагмент:\n{item.document.page_content}"
        )
    return "\n\n---\n\n".join(blocks)


def extract_sources(documents: list[RetrievedDocument]) -> list[SourceReference]:
    """Build deduplicated source list for the user-facing response."""
    seen: set[tuple[str, str]] = set()
    sources: list[SourceReference] = []

    for item in documents:
        metadata = item.document.metadata
        file_name = metadata.get("file_name", "unknown")
        module = metadata.get("module", "unknown")
        key = (module, file_name)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            SourceReference(
                file_name=file_name,
                module=module,
                resource_type=metadata.get("resource_type", "document"),
                excerpt=item.document.page_content[:300],
            )
        )
    return sources


def format_sources_for_display(sources: list[SourceReference]) -> str:
    if not sources:
        return "Источники не найдены в базе знаний."

    lines = ["**Использованные источники:**"]
    for index, source in enumerate(sources, start=1):
        lines.append(
            f"{index}. **{source.file_name}** — модуль `{source.module}`, "
            f"тип `{source.resource_type}`"
        )
    return "\n".join(lines)
