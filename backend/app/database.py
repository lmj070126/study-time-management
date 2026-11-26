
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

# 读取 backend/.env
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

required = [
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
]

missing = [key for key in required if not os.getenv(key)]
if missing:
    raise RuntimeError(
        f"Missing database configuration: {', '.join(missing)}"
    )

# URL.create 可以正确处理密码中的特殊字符
database_url = URL.create(
    drivername="mysql+pymysql",
    username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    database=os.environ["DB_NAME"],
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    echo=False,
    connect_args={
        "connect_timeout": 5,
        "init_command": "SET time_zone = '+00:00'",
    },
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    with SessionLocal() as db:
        yield db
