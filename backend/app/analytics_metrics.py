"""Pure calculations for the student's UTC+8 study dashboard.

The source of credited study minutes is study_records, not focus_sessions.
Records are attributed to the local calendar day of their start time.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Mapping

UTC_PLUS_8 = timezone(timedelta(hours=8))


def local_study_date(started_at: datetime) -> date:
    """Convert a database UTC DATETIME (naive or aware) to UTC+8 date."""
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return started_at.astimezone(UTC_PLUS_8).date()


def _coerce_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def build_overview(
    *,
    today_local: date,
    weekly_records: Iterable[Mapping],
    history_days: Iterable[date],
    task_total: int,
    task_done: int,
) -> dict:
    """Build a complete 7-local-calendar-day student statistics response.

    Weekly records must already be filtered by authenticated student and UTC
    time bounds. Efficiency is the unweighted mean of session self-ratings.
    """
    start_date = today_local - timedelta(days=6)
    days = [start_date + timedelta(days=offset) for offset in range(7)]
    daily_map = {
        day: {"date": day.isoformat(), "minutes": 0,
              "sessions": 0, "average_rating": None}
        for day in days
    }
    rating_sums = defaultdict(int)
    subject_map = {}
    total_rating = 0
    session_count = 0

    for record in weekly_records:
        started_day = local_study_date(record["started_at"])
        if started_day not in daily_map:
            continue
        minutes = int(record["minutes"])
        rating = int(record["rating"])
        if minutes <= 0 or not 1 <= rating <= 5:
            raise ValueError("Invalid recorded study minutes or self-rating")

        current_day = daily_map[started_day]
        current_day["minutes"] += minutes
        current_day["sessions"] += 1
        rating_sums[started_day] += rating
        total_rating += rating
        session_count += 1

        sid = int(record["subject_id"])
        if sid not in subject_map:
            subject_map[sid] = {
                "subject_id": sid,
                "subject_name": str(record["subject_name"]),
                "minutes": 0,
                "sessions": 0,
            }
        subject_map[sid]["minutes"] += minutes
        subject_map[sid]["sessions"] += 1

    for day in days:
        item = daily_map[day]
        if item["sessions"]:
            item["average_rating"] = round(
                rating_sums[day] / item["sessions"], 2
            )

    recorded_dates = {_coerce_date(day) for day in history_days}
    cursor = today_local if today_local in recorded_dates else today_local - timedelta(days=1)
    streak_days = 0
    while cursor in recorded_dates:
        streak_days += 1
        cursor -= timedelta(days=1)

    task_total = int(task_total)
    task_done = int(task_done)
    if task_total < 0 or not 0 <= task_done <= task_total:
        raise ValueError("Invalid task counts")

    return {
        "period": {
            "timezone": "UTC+08:00",
            "start_date": start_date.isoformat(),
            "end_date": today_local.isoformat(),
        },
        "summary": {
            "today_minutes": daily_map[today_local]["minutes"],
            "week_minutes": sum(item["minutes"] for item in daily_map.values()),
            "week_sessions": session_count,
            "week_avg_rating": (
                round(total_rating / session_count, 2) if session_count else None
            ),
            "streak_days": streak_days,
            "task_total": task_total,
            "task_done": task_done,
            "task_completion_rate": (
                round(task_done * 100 / task_total, 1) if task_total else 0.0
            ),
        },
        "daily": [daily_map[day] for day in days],
        "subjects": sorted(
            subject_map.values(),
            key=lambda item: (-item["minutes"], item["subject_name"]),
        ),
    }
