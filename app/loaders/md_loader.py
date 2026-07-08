from __future__ import annotations

from pathlib import Path

from app.loaders.base import BaseDocumentLoader, LoadedDocument
from app.utils.text_utils import clean_text


class MarkdownLoader(BaseDocumentLoader):
    """Load converted Markdown documents from the knowledge base."""

    extension = ".md"

    def load(self, file_path: Path, module: str) -> LoadedDocument:
        raw_text = file_path.read_text(encoding="utf-8")
        cleaned = clean_text(raw_text)
        metadata = self.build_metadata(file_path, module)
        return LoadedDocument(text=cleaned, metadata=metadata)
