#!/usr/bin/env python3
"""Run LMS Mock API server."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn

from app.utils.config import get_settings


def main() -> int:
    settings = get_settings()
    host = "127.0.0.1"
    port = 8000
    if settings.lms_api_url.startswith("http"):
        # Parse port from URL if possible
        from urllib.parse import urlparse

        parsed = urlparse(settings.lms_api_url)
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = parsed.port

    print(f"Starting LMS Mock API at http://{host}:{port}")
    uvicorn.run("app.lms.api:app", host="0.0.0.0", port=port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
