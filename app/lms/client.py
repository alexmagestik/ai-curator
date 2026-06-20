from __future__ import annotations

import json

import httpx

from app.lms.data_loader import load_assignments, load_course_info, load_schedule
from app.utils.config import Settings, get_settings


class LMSClient:
    """HTTP client for LMS Mock API with local JSON fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.lms_api_url.rstrip("/")

    def get_schedule(self) -> list[dict]:
        return self._fetch("/schedule", load_schedule)

    def get_assignments(self) -> list[dict]:
        return self._fetch("/assignments", load_assignments)

    def get_course_info(self) -> dict:
        return self._fetch("/course-info", load_course_info)

    def get_all_context(self) -> dict:
        return {
            "schedule": self.get_schedule(),
            "assignments": self.get_assignments(),
            "course_info": self.get_course_info(),
        }

    def _fetch(self, endpoint: str, fallback_loader):
        try:
            with httpx.Client(timeout=3.0) as client:
                response = client.get(f"{self.base_url}{endpoint}")
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return fallback_loader(self.settings)
