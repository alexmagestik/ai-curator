"""Read-only structural validation of converted Markdown files.

Adapted from the ``validate-md-output`` skill. Checks Markdown structure
(headings, tables, lists, parsing artefacts) and reports issues without
modifying anything. The RAG indexer uses :func:`validate_markdown_tree`
to skip clearly broken files (empty output) and to log warnings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FAIL = "FAIL"
WARN = "WARN"
INFO = "INFO"

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_LIST_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+\S")
_GARBLED_RE = re.compile(r"[\u25a1?\ufffd\u00a4]{3,}")


@dataclass(frozen=True)
class Issue:
    level: str
    rule: str
    message: str
    line: int | None = None


@dataclass
class FileReport:
    path: Path
    issues: list[Issue] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(i.level == FAIL for i in self.issues):
            return FAIL
        if any(i.level == WARN for i in self.issues):
            return WARN
        return "OK"

    @property
    def failed(self) -> bool:
        return self.status == FAIL


@dataclass
class ValidationReport:
    files: list[FileReport] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.files if f.status == "OK")

    @property
    def warn_count(self) -> int:
        return sum(1 for f in self.files if f.status == WARN)

    @property
    def fail_count(self) -> int:
        return sum(1 for f in self.files if f.status == FAIL)

    @property
    def failed_paths(self) -> list[Path]:
        return [f.path for f in self.files if f.failed]


def _count_columns(row: str) -> int:
    cells = row.strip().strip("|").split("|")
    return len([c for c in cells])


def validate_markdown_text(text: str, source_size: int | None = None) -> list[Issue]:
    """Run the structural rules over a single Markdown document."""
    issues: list[Issue] = []
    raw = text
    lines = text.splitlines()

    # R1 Empty
    if len(raw.strip()) < 100:
        issues.append(Issue(FAIL, "R1", "file is empty or shorter than 100 bytes"))
        return issues

    headings = [i for i, ln in enumerate(lines, 1) if _HEADING_RE.match(ln)]

    # R2 NoHeadings (warning: RAG chunking still works on plain text)
    if not headings:
        issues.append(Issue(WARN, "R2", "no headings (# ) in the whole file"))

    # R3 BrokenTable
    for idx, ln in enumerate(lines):
        if _TABLE_SEP_RE.match(ln):
            sep_cols = _count_columns(ln)
            header = lines[idx - 1] if idx > 0 else ""
            if "|" in header and _count_columns(header) != sep_cols:
                issues.append(
                    Issue(
                        FAIL,
                        "R3",
                        f"table separator columns ({sep_cols}) != header "
                        f"columns ({_count_columns(header)})",
                        idx + 1,
                    )
                )

    # R5 GarbledLine (unparsed CID glyphs)
    for i, ln in enumerate(lines, 1):
        if _GARBLED_RE.search(ln) or "[?0x" in ln:
            issues.append(Issue(FAIL, "R5", f"garbled/undecoded run: {ln[:40]!r}", i))

    # R8 ManyBlankLines
    blank = 0
    for i, ln in enumerate(lines, 1):
        if ln.strip():
            blank = 0
        else:
            blank += 1
            if blank >= 3:
                issues.append(Issue(WARN, "R8", "3+ consecutive blank lines", i))
                blank = 0

    # R6 ShortFile
    if source_size and source_size > 5000 and len(raw.encode("utf-8")) < 500:
        issues.append(
            Issue(WARN, "R6", f"output < 500 bytes for a {source_size} byte source")
        )

    # R11 NoTablesNoLists
    has_table = any(_TABLE_SEP_RE.match(ln) for ln in lines)
    has_list = any(_LIST_RE.match(ln) for ln in lines)
    if not has_table and not has_list:
        issues.append(Issue(INFO, "R11", "no tables and no lists"))

    return issues


def validate_markdown_file(path: Path, source_size: int | None = None) -> FileReport:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return FileReport(path, [Issue(FAIL, "R0", f"cannot read file: {exc}")])
    return FileReport(path, validate_markdown_text(text, source_size))


def validate_markdown_tree(md_root: Path) -> ValidationReport:
    """Validate every ``.md`` file under ``md_root`` recursively."""
    report = ValidationReport()
    if not md_root.exists():
        return report
    for path in sorted(md_root.rglob("*.md")):
        if path.is_file():
            report.files.append(validate_markdown_file(path))
    return report


def format_report(report: ValidationReport) -> str:
    lines = [
        f"Files checked: {len(report.files)}",
        f"  OK:   {report.ok_count}",
        f"  WARN: {report.warn_count}",
        f"  FAIL: {report.fail_count}",
    ]
    for fr in report.files:
        if fr.status == "OK":
            continue
        lines.append("")
        lines.append(f"[{fr.status}] {fr.path}")
        for issue in fr.issues:
            loc = f" line {issue.line}" if issue.line else ""
            lines.append(f"    {issue.rule}{loc}: {issue.message}")
    return "\n".join(lines)
