from __future__ import annotations

from fastapi import FastAPI

from app.lms.data_loader import load_assignments, load_course_info, load_schedule

app = FastAPI(title="LMS Mock API", version="1.0.0")


@app.get("/schedule")
def get_schedule() -> list[dict]:
    return load_schedule()


@app.get("/assignments")
def get_assignments() -> list[dict]:
    return load_assignments()


@app.get("/course-info")
def get_course_info() -> dict:
    return load_course_info()
