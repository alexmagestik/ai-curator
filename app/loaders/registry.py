from __future__ import annotations

from pathlib import Path

from app.loaders.base import BaseDocumentLoader, LoadedDocument
from app.loaders.odt_loader import ODTLoader

LOADERS: dict[str, BaseDocumentLoader] = {
    ODTLoader.extension: ODTLoader(),
}


def get_loader_for_path(file_path: Path) -> BaseDocumentLoader | None:
    return LOADERS.get(file_path.suffix.lower())


def scan_knowledge_base(
    knowledge_base_path: Path,
    supported_extensions: tuple[str, ...],
) -> list[LoadedDocument]:
    """Recursively scan module folders and load supported documents."""
    if not knowledge_base_path.exists():
        return []

    documents: list[LoadedDocument] = []
    for module_dir in sorted(knowledge_base_path.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("."):
            continue

        module_name = module_dir.name
        for file_path in sorted(module_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in supported_extensions:
                continue

            loader = get_loader_for_path(file_path)
            if loader is None:
                continue

            documents.append(loader.load(file_path, module_name))

    return documents
