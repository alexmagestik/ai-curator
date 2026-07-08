"""Convert knowledge-base sources (ODT/PDF) into a mirrored Markdown tree.

Pipeline: sources in ``knowledge_base/`` -> Markdown in ``knowledge_base_md/``
with the module folder structure preserved. The RAG indexer converts, then
validates, then indexes the Markdown output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.conversion import odt_to_md, pdf_to_md

Converter = Callable[[Path], str]

CONVERTERS: dict[str, Converter] = {
    ".odt": odt_to_md.convert,
    ".pdf": pdf_to_md.convert,
}


@dataclass
class ConversionResult:
    converted: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def converted_count(self) -> int:
        return len(self.converted)

    @property
    def error_count(self) -> int:
        return len(self.errors)


def _target_md_path(source: Path, sources_root: Path, md_root: Path) -> Path:
    try:
        rel = source.resolve().relative_to(sources_root.resolve())
    except ValueError:
        rel = Path(source.name)
    return md_root / rel.with_suffix(".md")


def convert_file(source: Path, sources_root: Path, md_root: Path) -> Path:
    """Convert a single source file to Markdown, mirroring the folder layout."""
    converter = CONVERTERS.get(source.suffix.lower())
    if converter is None:
        raise ValueError(f"Unsupported source extension: {source.suffix}")
    target = _target_md_path(source, sources_root, md_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(converter(source), encoding="utf-8")
    return target


def _needs_conversion(source: Path, target: Path) -> bool:
    if not target.exists():
        return True
    try:
        return source.stat().st_mtime > target.stat().st_mtime
    except OSError:
        return True


def convert_knowledge_base(
    sources_root: Path,
    md_root: Path,
    source_extensions: tuple[str, ...],
    force: bool = False,
) -> ConversionResult:
    """Convert every supported source under ``sources_root`` into ``md_root``.

    Conversion is incremental: a source is skipped when its mirror Markdown is
    newer, unless ``force`` is set.
    """
    result = ConversionResult()
    if not sources_root.exists():
        return result

    exts = {ext.lower() for ext in source_extensions if ext.lower() in CONVERTERS}
    for source in sorted(sources_root.rglob("*")):
        if not source.is_file() or source.suffix.lower() not in exts:
            continue
        target = _target_md_path(source, sources_root, md_root)
        if not force and not _needs_conversion(source, target):
            result.skipped.append(target)
            continue
        try:
            converter = CONVERTERS[source.suffix.lower()]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(converter(source), encoding="utf-8")
            result.converted.append(target)
        except Exception as exc:  # noqa: BLE001 - report per-file, keep going
            result.errors.append((source, str(exc)))
    return result
