from __future__ import annotations

from datetime import date, timedelta


def build_date_filter(
    start_date: date | None,
    end_date: date | None,
    *,
    column: str = "timestamp",
) -> tuple[str, list[str]]:
    """Return SQL condition and params for inclusive date range (YYYY-MM-DD)."""
    parts: list[str] = []
    params: list[str] = []
    if start_date is not None:
        parts.append(f"substr({column}, 1, 10) >= ?")
        params.append(start_date.isoformat())
    if end_date is not None:
        parts.append(f"substr({column}, 1, 10) <= ?")
        params.append(end_date.isoformat())
    if not parts:
        return "1=1", []
    return " AND ".join(parts), params


def fill_requests_by_day(
    start_date: date | None,
    end_date: date | None,
    rows: list[tuple[str, int]],
) -> list[tuple[str, int]]:
    if start_date is None or end_date is None:
        return rows
    by_day = dict(rows)
    filled: list[tuple[str, int]] = []
    current = start_date
    while current <= end_date:
        key = current.isoformat()
        filled.append((key, by_day.get(key, 0)))
        current += timedelta(days=1)
    return filled
