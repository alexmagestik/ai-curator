from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedDocument:
    text: str
    metadata: dict[str, str]


class BaseDocumentLoader(ABC):
    """Abstract loader interface for future PDF/DOCX/HTML/MD support."""

    extension: str

    @abstractmethod
    def load(self, file_path: Path, module: str) -> LoadedDocument:
        """Load a single document and return text with metadata."""

    def build_metadata(self, file_path: Path, module: str) -> dict[str, str]:
        from datetime import datetime, timezone

        from app.utils.text_utils import infer_resource_type, infer_topic

        stat = file_path.stat()
        file_name = file_path.name
        return {
            "module": module,
            "file_name": file_name,
            "resource_type": infer_resource_type(file_name),
            "topic": infer_topic(file_name),
            "source_path": str(file_path.resolve()),
            "last_modified": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
        }
