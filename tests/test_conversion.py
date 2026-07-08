from __future__ import annotations

from pathlib import Path

import pytest
from odf.opendocument import OpenDocumentText
from odf.text import H, P

from app.conversion.pdf_to_md import (
    _dedupe_consecutive,
    _detect_running_lines,
    _is_droppable_line,
    _norm_key,
    _page_to_md,
)
from app.conversion.pipeline import convert_file, convert_knowledge_base
from app.conversion.validator import (
    FAIL,
    validate_markdown_text,
    validate_markdown_tree,
)
from app.loaders.md_loader import MarkdownLoader
from app.loaders.registry import scan_knowledge_base


def _write_odt(path: Path, heading: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = OpenDocumentText()
    document.text.addElement(H(outlinelevel=1, text=heading))
    document.text.addElement(P(text=body))
    document.save(str(path))


@pytest.fixture
def knowledge_base(tmp_path: Path) -> tuple[Path, Path]:
    sources = tmp_path / "knowledge_base"
    md_root = tmp_path / "knowledge_base_md"
    _write_odt(
        sources / "module_01" / "lecture_01.odt",
        "Введение в Python",
        "Python — высокоуровневый язык программирования для backend-разработки. "
        "Он широко используется для веб-серверов, автоматизации, анализа данных "
        "и машинного обучения. В этом модуле разбираются переменные, функции, "
        "модули и виртуальные окружения.",
    )
    return sources, md_root


def test_convert_file_produces_markdown(knowledge_base: tuple[Path, Path]) -> None:
    sources, md_root = knowledge_base
    source = sources / "module_01" / "lecture_01.odt"

    out = convert_file(source, sources, md_root)

    assert out == md_root / "module_01" / "lecture_01.md"
    text = out.read_text(encoding="utf-8")
    assert "# Введение в Python" in text
    assert "backend" in text.lower()


def test_convert_knowledge_base_mirrors_structure(
    knowledge_base: tuple[Path, Path]
) -> None:
    sources, md_root = knowledge_base

    result = convert_knowledge_base(sources, md_root, (".odt", ".pdf"))

    assert result.converted_count == 1
    assert result.error_count == 0
    assert (md_root / "module_01" / "lecture_01.md").exists()


def test_convert_knowledge_base_is_incremental(
    knowledge_base: tuple[Path, Path]
) -> None:
    sources, md_root = knowledge_base

    first = convert_knowledge_base(sources, md_root, (".odt",))
    second = convert_knowledge_base(sources, md_root, (".odt",))

    assert first.converted_count == 1
    assert second.converted_count == 0
    assert len(second.skipped) == 1


def test_markdown_loader_and_scan(knowledge_base: tuple[Path, Path]) -> None:
    sources, md_root = knowledge_base
    convert_knowledge_base(sources, md_root, (".odt",))

    documents = scan_knowledge_base(md_root, (".md",))
    assert len(documents) == 1
    doc = documents[0]
    assert doc.metadata["module"] == "module_01"
    assert doc.metadata["file_name"] == "lecture_01.md"
    assert "Python" in doc.text

    loaded = MarkdownLoader().load(
        md_root / "module_01" / "lecture_01.md", module="module_01"
    )
    assert "# Введение в Python" in loaded.text


def test_validate_flags_empty_file() -> None:
    issues = validate_markdown_text("# tiny")
    assert any(i.rule == "R1" and i.level == FAIL for i in issues)


def test_validate_flags_garbled_run() -> None:
    text = "# Заголовок\n\n" + "нормальный текст " * 20 + "\n\n[?0x00410042] далее\n"
    issues = validate_markdown_text(text)
    assert any(i.rule == "R5" and i.level == FAIL for i in issues)


def test_validate_accepts_clean_document() -> None:
    body = "Это достаточно длинный и корректный markdown-документ. " * 5
    text = f"# Заголовок\n\n{body}\n\n- пункт один\n- пункт два\n"
    issues = validate_markdown_text(text)
    assert all(i.level != FAIL for i in issues)


def test_validate_markdown_tree(knowledge_base: tuple[Path, Path]) -> None:
    sources, md_root = knowledge_base
    convert_knowledge_base(sources, md_root, (".odt",))

    report = validate_markdown_tree(md_root)
    assert len(report.files) == 1
    assert report.fail_count == 0


# --- PDF cleanup: page numbers, footers, headers, duplicates ---


@pytest.mark.parametrize(
    "line",
    [
        "5",
        "- 5 -",
        "12",
        "Стр. 5",
        "стр 5",
        "Страница 5 из 10",
        "Page 12",
        "page 3 of 20",
        "5 из 10",
        "5/10",
        "© 2019 Компания",
        "All rights reserved",
    ],
)
def test_droppable_lines(line: str) -> None:
    assert _is_droppable_line(line) is True


@pytest.mark.parametrize(
    "line",
    [
        "5 важных принципов промптинга",
        "Модуль 3. No-code интеграции",
        "Это обычный абзац с содержательным текстом.",
    ],
)
def test_non_droppable_lines(line: str) -> None:
    assert _is_droppable_line(line) is False


def test_detect_running_lines_ignores_page_numbers() -> None:
    topics = ["алгоритмы", "структуры данных", "сети", "базы данных"]
    pages_lines = [
        [(10.0, f"Модуль 1 стр {i + 1}"), (10.0, f"Тема про {topics[i]}")]
        for i in range(4)
    ]

    repeated = _detect_running_lines(pages_lines)

    assert _norm_key("Модуль 1 стр 1") in repeated
    assert _norm_key("Тема про алгоритмы") not in repeated


def test_page_to_md_drops_page_numbers_and_markers() -> None:
    lines = [
        (14.0, "Заголовок урока"),
        (10.0, "Обычный текст первого абзаца."),
        (10.0, "12"),
    ]

    result = _page_to_md(lines, 1, set())

    assert "<!-- page" not in result
    assert "## Заголовок урока" in result
    assert "Обычный текст первого абзаца." in result
    assert "12" not in result.split()


def test_dedupe_consecutive_collapses_repeats() -> None:
    lines = ["## Заголовок", "", "## Заголовок", "текст", "текст"]

    out = _dedupe_consecutive(lines)

    assert out.count("## Заголовок") == 1
    assert out.count("текст") == 1
