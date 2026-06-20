from __future__ import annotations

from pathlib import Path

from odf import teletype, text
from odf.opendocument import load

from app.loaders.base import BaseDocumentLoader, LoadedDocument
from app.utils.text_utils import clean_text


class ODTLoader(BaseDocumentLoader):
    extension = ".odt"

    def load(self, file_path: Path, module: str) -> LoadedDocument:
        document = load(str(file_path))
        paragraphs = document.getElementsByType(text.P)
        raw_text = "\n".join(teletype.extractText(paragraph) for paragraph in paragraphs)
        cleaned = clean_text(raw_text)
        metadata = self.build_metadata(file_path, module)
        return LoadedDocument(text=cleaned, metadata=metadata)
