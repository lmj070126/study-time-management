"""Focus sessions and completed study records for Study Time Management.

Time is authoritative on MySQL (UTC_TIMESTAMP(6)); no client supplied duration.
One completed record per session is enforced in the database and by row locking.
"""

import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import require_role
from .database import get_db

router = APIRouter(prefix="/api/focus", tags=["Focus sessions"])


class StartFocusRequest(BaseModel):
    task_id: int = Field(gt=0)
    planned_minutes: int = Field(default=25, ge=1, le=120)
    rest_minutes: int = Field(default=5, ge=1, le=60)


class CompleteFocusRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


def _own_session(db: Session, session_id: int, student_id: int):
    """Get and lock session, enforcing resource ownership (404 on mismatch)."""
    row = db.execute(
        text("""
            SELECT f.id, f.student_id, f.task_id, f.started_at,
                   f.ended_at, f.planned_minutes, f.rest_minutes,
                   f.status, t.subject_id
            FROM focus_sessions AS f
            JOIN tasks AS t ON t.id = f.task_id
            WHERE f.id = :session_id
              AND f.student_id = :student_id
              AND t.student_id = :student_id
            FOR UPDATE
        """),
        {"session_id": session_id, "student_id": student_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found or inaccessible")
    return row


def _record(db: Session, session_id: int, student_id: int):
    row = db.execute(
        text("""
            SELECT id, focus_session_id, minutes, rating, started_at, ended_at
            FROM study_records
            WHERE focus_session_id = :session_id AND student_id = :student_id
        """),
        {"session_id": session_id, "student_id": student_id},
    ).mappings().first()
    return dict(row) if row else None


@router.post("/start", status_code=201)
def start_focus(
    data: StartFocusRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("student")),
):
    uid = user["id"]
    try:
        # Serialize starts for the same student across concurrent requests.
        db.execute(
            text("SELECT id FROM users WHERE id = :uid FOR UPDATE"),
            {"uid": uid},
        ).one()
        active = db.execute(
            text("""
                SELECT id FROM focus_sessions
                WHERE student_id = :uid
                  AND status IN ('pending', 'running', 'paused')
                LIMIT 1
            """),
            {"uid": uid},
        ).scalar_one_or_none()
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail=f"An active session already exists: {active}",
            )
        task = db.execute(
            text("""
                SELECT id FROM tasks
                WHERE id = :task_id AND student_id = :uid
                  AND status IN ('todo', 'in_progress')
                FOR UPDATE
            """),
            {"task_id": data.task_id, "uid": uid},
        ).scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found or unavailable")

        result = db.execute(
            text("""
                INSERT INTO focus_sessions
                    (student_id, task_id, planned_minutes, rest_minutes,
                     started_at, status)
                VALUES
                    (:uid, :task_id, :planned_minutes, :rest_minutes,
                     UTC_TIMESTAMP(6), 'running')
            """),
            {
                "uid": uid,
                "task_id": data.task_id,
                "planned_minutes": data.planned_minutes,
                "rest_minutes": data.rest_minutes,
            },
        )
        session_id = result.lastrowid
        db.execute(
            text("""
                UPDATE tasks SET status = 'in_progress'
                WHERE id = :task_id AND student_id = :uid AND status = 'todo'
            """),
            {"task_id": data.task_id, "uid": uid},
        )
        db.commit()
        return {
            "session_id": session_id,
            "task_id": data.task_id,
            "planned_minutes": data.planned_minutes,
            "rest_minutes": data.rest_minutes,
            "status": "running",
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to start session")


@router.post("/{session_id}/complete")
def complete_focus(
    session_id: int,
    data: CompleteFocusRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("student")),
):
    uid = user["id"]
    try:
        session = _own_session(db, session_id, uid)
        if session["status"] == "completed":
            previous = _record(db, session_id, uid)
            if previous is None:
                raise HTTPException(status_code=409, detail="Completed session is missing its record")
            db.rollback()  # Release FOR UPDATE lock; no mutation on retry.
            return {**previous, "status": "completed", "already_completed": True}
        if session["status"] != "running" or session["started_at"] is None:
            raise HTTPException(status_code=409, detail="Session is not running")

        # Both timestamps are MySQL UTC DATETIME values; never trust client time.
        now = db.execute(text("SELECT UTC_TIMESTAMP(6)")).scalar_one()
        elapsed_seconds = (now - session["started_at"]).total_seconds()
        required_seconds = session["planned_minutes"] * 60
        if elapsed_seconds < required_seconds:
            remaining = math.ceil(required_seconds - elapsed_seconds)
            raise HTTPException(
                status_code=409,
                detail=f"Focus time not reached; {remaining} seconds remaining",
            )
        # Never count time beyond the configured focus interval as study time.
        credited_minutes = min(
            session["planned_minutes"], int(elapsed_seconds // 60)
        )
        db.execute(
            text("""
                UPDATE focus_sessions SET status = 'completed', ended_at = :ended_at
                WHERE id = :session_id AND student_id = :uid AND status = 'running'
            """),
            {"ended_at": now, "session_id": session_id, "uid": uid},
        )
        result = db.execute(
            text("""
                INSERT INTO study_records
                    (focus_session_id, student_id, subject_id,
                     started_at, ended_at, minutes, rating)
                VALUES
                    (:session_id, :uid, :subject_id,
                     :started_at, :ended_at, :minutes, :rating)
            """),
            {
                "session_id": session_id,
                "uid": uid,
                "subject_id": session["subject_id"],
                "started_at": session["started_at"],
                "ended_at": now,
                "minutes": credited_minutes,
                "rating": data.rating,
            },
        )
        record_id = result.lastrowid
        db.commit()  # Update and insert commit atomically.
        return {
            "id": record_id,
            "focus_session_id": session_id,
            "minutes": credited_minutes,
            "rating": data.rating,
            "started_at": session["started_at"],
            "ended_at": now,
            "status": "completed",
            "already_completed": False,
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to complete session")


@router.post("/{session_id}/abandon")
def abandon_focus(
    session_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("student")),
):
    uid = user["id"]
    try:
        session = _own_session(db, session_id, uid)
        if session["status"] == "completed":
            raise HTTPException(status_code=409, detail="Completed session cannot be abandoned")
        if session["status"] == "abandoned":
            db.rollback()
            return {"session_id": session_id, "status": "abandoned"}
        db.execute(
            text("""
                UPDATE focus_sessions
                SET status = 'abandoned', ended_at = UTC_TIMESTAMP(6)
                WHERE id = :session_id AND student_id = :uid
            """),
            {"session_id": session_id, "uid": uid},
        )
        db.commit()
        return {"session_id": session_id, "status": "abandoned"}
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Unable to abandon session")


@router.get("")
def my_sessions(
    db: Session = Depends(get_db),
    user=Depends(require_role("student")),
):
    rows = db.execute(
        text("""
            SELECT f.id, f.task_id, t.title AS task_title,
                   f.status, f.planned_minutes, f.rest_minutes,
                   f.started_at, f.ended_at
            FROM focus_sessions AS f
            JOIN tasks AS t ON t.id = f.task_id
            WHERE f.student_id = :uid
            ORDER BY f.id DESC LIMIT 30
        """),
        {"uid": user["id"]},
    ).mappings().all()
    return [dict(row) for row in rows]


@router.get("/records")
def my_study_records(
    db: Session = Depends(get_db),
    user=Depends(require_role("student")),
):
    rows = db.execute(
        text("""
            SELECT r.id, r.focus_session_id, r.subject_id,
                   s.subject_name, r.started_at, r.ended_at,
                   r.minutes, r.rating
            FROM study_records AS r
            JOIN subjects AS s ON s.id = r.subject_id
            WHERE r.student_id = :uid
            ORDER BY r.started_at DESC, r.id DESC
            LIMIT 100
        """),
        {"uid": user["id"]},
    ).mappings().all()
    return [dict(row) for row in rows]
