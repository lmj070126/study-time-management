"""Student-only analytics sourced from recorded, completed study sessions."""

from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .analytics_metrics import UTC_PLUS_8, build_overview
from .auth import require_role
from .database import get_db

router = APIRouter(prefix="/api/analytics", tags=["学习数据分析"])


class Period(BaseModel):
    timezone: str
    start_date: str
    end_date: str


class Summary(BaseModel):
    today_minutes: int = Field(ge=0)
    week_minutes: int = Field(ge=0)
    week_sessions: int = Field(ge=0)
    week_avg_rating: float | None = Field(default=None, ge=1, le=5)
    streak_days: int = Field(ge=0)
    task_total: int = Field(ge=0)
    task_done: int = Field(ge=0)
    task_completion_rate: float = Field(ge=0, le=100)


class DailyItem(BaseModel):
    date: str
    minutes: int = Field(ge=0)
    sessions: int = Field(ge=0)
    average_rating: float | None = Field(default=None, ge=1, le=5)


class SubjectItem(BaseModel):
    subject_id: int
    subject_name: str
    minutes: int = Field(ge=0)
    sessions: int = Field(ge=0)


class AnalyticsOverview(BaseModel):
    period: Period
    summary: Summary
    daily: list[DailyItem]
    subjects: list[SubjectItem]


@router.get("/overview", response_model=AnalyticsOverview)
def overview(
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """Last 7 UTC+8 calendar days, including today, for the logged-in student.

    MySQL study_records.started_at is stored as UTC DATETIME. Use index-friendly
    UTC boundaries so local day aggregation is correct around midnight.
    """
    today = datetime.now(UTC_PLUS_8).date()
    start = today - timedelta(days=6)
    start_local = datetime.combine(start, time.min, tzinfo=UTC_PLUS_8)
    end_local = datetime.combine(today + timedelta(days=1), time.min, tzinfo=UTC_PLUS_8)
    utc_start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    utc_end = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    uid = user["id"]

    try:
        weekly_records = db.execute(
            text("""
                SELECT r.subject_id, s.subject_name,
                       r.started_at, r.minutes, r.rating
                FROM study_records AS r
                JOIN subjects AS s ON s.id = r.subject_id
                WHERE r.student_id = :uid
                  AND r.started_at >= :utc_start
                  AND r.started_at < :utc_end
                ORDER BY r.started_at, r.id
            """),
            {"uid": uid, "utc_start": utc_start, "utc_end": utc_end},
        ).mappings().all()

        # One local study date per day; study_records cannot contain duplicate
        # records for the same focus session (database uniqueness constraint).
        history_days = db.execute(
            text("""
                SELECT DISTINCT DATE(DATE_ADD(started_at, INTERVAL 8 HOUR))
                                AS local_day
                FROM study_records
                WHERE student_id = :uid
            """),
            {"uid": uid},
        ).scalars().all()

        task_counts = db.execute(
            text("""
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(CASE WHEN status = 'done'
                               THEN 1 ELSE 0 END), 0) AS completed
                FROM tasks
                WHERE student_id = :uid
                  AND status <> 'cancelled'
            """),
            {"uid": uid},
        ).mappings().one()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="学习统计暂时不可用") from exc

    return build_overview(
        today_local=today,
        weekly_records=weekly_records,
        history_days=history_days,
        task_total=task_counts["total"],
        task_done=task_counts["completed"],
    )
