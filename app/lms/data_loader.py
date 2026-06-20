from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.utils.config import Settings, get_settings


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_schedule(settings: Settings | None = None) -> list[dict]:
    settings = settings or get_settings()
    return _read_json(settings.lms_data_path / "schedule.json")


def load_assignments(settings: Settings | None = None) -> list[dict]:
    settings = settings or get_settings()
    return _read_json(settings.lms_data_path / "assignments.json")


def load_course_info(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return _read_json(settings.lms_data_path / "course_info.json")
