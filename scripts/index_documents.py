#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.indexer import build_index  # noqa: E402


def main() -> int:
    result = build_index()
    print("Indexing completed.")
    print(f"  Source files scanned: {result.source_files}")
    print(f"  New chunks indexed:   {result.chunks_indexed}")
    print(f"  Collection:             {result.collection_name}")
    print(f"  Vector store path:      {result.vector_db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
