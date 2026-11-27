
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import require_role
from .database import get_db

router = APIRouter(prefix="/api/tasks", tags=["学习任务"])

TaskStatus = Literal[
    "todo", "in_progress", "done", "cancelled"
]


def clean_title(value):
    if value is None:
        return value
    value = value.strip()
    if not value:
        raise ValueError("任务标题不能为空")
    return value


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=3000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        return clean_title(value)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    status: TaskStatus | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        return clean_title(value)


class TaskView(BaseModel):
    id: int
    subject_id: int
    subject_name: str
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


def find_own_task(db: Session, task_id: int, student_id: int):
    row = db.execute(
        text("""
            SELECT t.id, t.subject_id, s.subject_name,
                   t.title, t.description, t.status,
                   t.created_at, t.updated_at
            FROM tasks AS t
            JOIN subjects AS s ON s.id = t.subject_id
            WHERE t.id = :task_id
              AND t.student_id = :student_id
        """),
        {"task_id": task_id, "student_id": student_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="任务不存在或无权访问",
        )

    return dict(row)


@router.get("/subjects")
def list_subjects(
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text("""
            SELECT id, subject_name
            FROM subjects
            WHERE enabled = TRUE
            ORDER BY id
        """)
    ).mappings().all()

    return [dict(row) for row in rows]


@router.get("", response_model=list[TaskView])
def list_my_tasks(
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text("""
            SELECT t.id, t.subject_id, s.subject_name,
                   t.title, t.description, t.status,
                   t.created_at, t.updated_at
            FROM tasks AS t
            JOIN subjects AS s ON s.id = t.subject_id
            WHERE t.student_id = :student_id
            ORDER BY t.created_at DESC, t.id DESC
        """),
        {"student_id": user["id"]},
    ).mappings().all()

    return [dict(row) for row in rows]


@router.post("", response_model=TaskView, status_code=201)
def create_task(
    data: TaskCreate,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    subject = db.execute(
        text("""
            SELECT id FROM subjects
            WHERE id = :subject_id AND enabled = TRUE
        """),
        {"subject_id": data.subject_id},
    ).first()

    if subject is None:
        raise HTTPException(
            status_code=422,
            detail="科目不存在或已停用",
        )

    try:
        result = db.execute(
            text("""
                INSERT INTO tasks
                    (student_id, subject_id, title,
                     description, status)
                VALUES
                    (:student_id, :subject_id, :title,
                     :description, 'todo')
            """),
            {
                "student_id": user["id"],
                "subject_id": data.subject_id,
                "title": data.title,
                "description": data.description,
            },
        )

        task_id = result.lastrowid
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="创建任务失败",
        )

    return find_own_task(db, task_id, user["id"])


@router.patch("/{task_id}", response_model=TaskView)
def update_task(
    task_id: int,
    data: TaskUpdate,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    # 先检查任务所有权
    find_own_task(db, task_id, user["id"])

    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="没有提供需要修改的字段",
        )

    for field in ("title", "status"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field}不能设置为空",
            )

    # 字段名由Pydantic模型限定，不接受任意SQL字段
    assignments = ", ".join(
        f"{field} = :{field}" for field in changes
    )

    params = {
        **changes,
        "task_id": task_id,
        "student_id": user["id"],
    }

    try:
        db.execute(
            text(f"""
                UPDATE tasks
                SET {assignments}
                WHERE id = :task_id
                  AND student_id = :student_id
            """),
            params,
        )
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="修改任务失败",
        )

    return find_own_task(db, task_id, user["id"])


@router.delete("/{task_id}", response_model=TaskView)
def cancel_task(
    task_id: int,
    user=Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    # 不直接删除数据，保留历史学习记录
    find_own_task(db, task_id, user["id"])

    try:
        db.execute(
            text("""
                UPDATE tasks
                SET status = 'cancelled'
                WHERE id = :task_id
                  AND student_id = :student_id
            """),
            {
                "task_id": task_id,
                "student_id": user["id"],
            },
        )
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="取消任务失败",
        )

    return find_own_task(db, task_id, user["id"])
