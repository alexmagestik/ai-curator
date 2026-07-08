#!/usr/bin/env python3
"""Validate the converted Markdown tree (structure spot-check, read-only).

Usage:
    python scripts/validate_md.py            # validate knowledge_base_md/
    python scripts/validate_md.py "<dir>"    # validate a specific directory

Does not modify any files. Exit code is non-zero when a FAIL is found.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.conversion.validator import format_report, validate_markdown_tree  # noqa: E402
from app.utils.config import get_settings  # noqa: E402


def main(argv: list[str]) -> int:
    if argv:
        md_root = Path(argv[0]).resolve()
    else:
        md_root = get_settings().knowledge_base_md_path

    report = validate_markdown_tree(md_root)
    print(format_report(report))
    return 1 if report.fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
