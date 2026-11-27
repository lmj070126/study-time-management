
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine
from .auth import router as auth_router
from .tasks import router as tasks_router
from .focus import router as focus_router

# 创建 FastAPI 应用
app = FastAPI(
    title="智学时光 API",
    description="学生学习时间管理与效率分析系统",
    version="0.1.0",
)

# 注册登录与权限接口
app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(focus_router)


@app.get("/api/health", tags=["系统检查"])
def health_check():
    return {
        "status": "ok",
        "service": "study-time-api",
        "version": "0.1.0",
    }


@app.get("/api/db-health", tags=["系统检查"])
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )
