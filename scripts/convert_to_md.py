#!/usr/bin/env python3
"""Convert knowledge-base sources (ODT/PDF) into a mirrored Markdown tree.

Usage:
    python scripts/convert_to_md.py                # convert all changed sources
    python scripts/convert_to_md.py --force        # reconvert everything
    python scripts/convert_to_md.py "<path.odt>"   # convert specific files

Sources live in ``knowledge_base/`` and Markdown output goes to
``knowledge_base_md/`` (paths configurable via config.yaml / .env).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.conversion.pipeline import convert_file, convert_knowledge_base  # noqa: E402
from app.utils.config import get_settings  # noqa: E402


def main(argv: list[str]) -> int:
    settings = get_settings()
    force = "--force" in argv
    targets = [a for a in argv if not a.startswith("--")]

    if targets:
        errors = 0
        for raw in targets:
            source = Path(raw).resolve()
            if not source.exists():
                print(f"Skip (missing): {source}", file=sys.stderr)
                errors += 1
                continue
            try:
                out = convert_file(
                    source, settings.knowledge_base_path, settings.knowledge_base_md_path
                )
                print(f"{source} -> {out}")
            except Exception as exc:  # noqa: BLE001
                print(f"Error ({source}): {exc}", file=sys.stderr)
                errors += 1
        return 1 if errors else 0

    result = convert_knowledge_base(
        settings.knowledge_base_path,
        settings.knowledge_base_md_path,
        settings.supported_extensions,
        force=force,
    )
    print("Conversion completed.")
    print(f"  Converted: {result.converted_count}")
    print(f"  Skipped (up to date): {len(result.skipped)}")
    print(f"  Errors: {result.error_count}")
    for source, message in result.errors:
        print(f"    {source}: {message}", file=sys.stderr)
    print(f"  Output: {settings.knowledge_base_md_path}")
    print("\nValidate the result: python scripts/validate_md.py")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
