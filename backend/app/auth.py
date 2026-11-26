
import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import (
    VerifyMismatchError,
    VerificationError,
    InvalidHashError,
)
from fastapi import (
    APIRouter, Depends, HTTPException, status
)
from fastapi.security import (
    HTTPBearer, HTTPAuthorizationCredentials
)
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db

router = APIRouter(prefix="/api/auth", tags=["登录与权限"])
bearer = HTTPBearer(auto_error=False)
password_hasher = PasswordHasher()

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "study-time-api"
JWT_AUDIENCE = "study-time-client"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def auth_error():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="用户名、密码或登录凭证无效",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_jwt_secret():
    secret = os.getenv("JWT_SECRET")
    if not secret or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET 未配置或长度不足32字符"
        )
    return secret


def create_access_token(user_id: int):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=1),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    row = db.execute(
        text("""
            SELECT id, username, password_hash,
                   role, is_active
            FROM users
            WHERE username = :username
            LIMIT 1
        """),
        {"username": data.username},
    ).mappings().first()

    if not row or not row["is_active"]:
        raise auth_error()

    try:
        valid = password_hasher.verify(
            row["password_hash"],
            data.password,
        )
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        raise auth_error()

    if not valid:
        raise auth_error()

    return {
        "access_token": create_access_token(row["id"]),
        "token_type": "bearer",
        "expires_in": 3600,
        "role": row["role"],
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None =
        Depends(bearer),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise auth_error()

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={
                "require": [
                    "sub", "exp", "iat", "iss", "aud"
                ]
            },
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise auth_error()

    row = db.execute(
        text("""
            SELECT id, username, role,
                   class_id, alias, is_active
            FROM users
            WHERE id = :user_id
        """),
        {"user_id": user_id},
    ).mappings().first()

    if not row or not row["is_active"]:
        raise auth_error()

    return dict(row)


def require_role(*allowed_roles):
    def check_role(user=Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="没有访问权限",
            )
        return user

    return check_role


@router.get("/me")
def get_my_info(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "class_id": user["class_id"],
        "alias": user["alias"],
    }


# 以下三个接口供开发阶段测试权限使用
@router.get("/student-check")
def student_check(user=Depends(require_role("student"))):
    return {"result": "allowed", "role": user["role"]}


@router.get("/teacher-check")
def teacher_check(user=Depends(require_role("teacher"))):
    return {"result": "allowed", "role": user["role"]}


@router.get("/admin-check")
def admin_check(user=Depends(require_role("admin"))):
    return {"result": "allowed", "role": user["role"]}
