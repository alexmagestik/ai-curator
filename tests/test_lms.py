from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.lms.api import app
from app.lms.data_loader import load_assignments, load_course_info, load_schedule
from app.utils.config import get_settings


def test_lms_api_endpoints(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LMS_DATA_PATH", str(settings.lms_data_path))
    get_settings.cache_clear()

    client = TestClient(app)

    schedule = client.get("/schedule")
    assert schedule.status_code == 200
    assert isinstance(schedule.json(), list)

    assignments = client.get("/assignments")
    assert assignments.status_code == 200
    assert isinstance(assignments.json(), list)

    course_info = client.get("/course-info")
    assert course_info.status_code == 200
    assert "course" in course_info.json()

    get_settings.cache_clear()


def test_lms_data_loader(settings) -> None:
    assert load_schedule(settings)
    assert load_assignments(settings)
    assert load_course_info(settings)["course"] == "Python Backend"
