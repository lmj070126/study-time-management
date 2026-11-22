"""Seed local MySQL for Project 20. Only touches dedicated DEMO users and tasks.

Usage (Windows PowerShell):
  python -m pip install -r scripts/requirements-seed.txt
  python scripts/seed_demo.py --self-test
  python scripts/seed_demo.py

Security: passwords are prompted, never stored in the script or git repository.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from getpass import getpass
from zoneinfo import ZoneInfo

DB_NAME = "study_time_db"
DB_HOST = "127.0.0.1"  # Deliberately local-only
DB_PORT = 3306
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
WEEKLY_MINUTES = (100, 120, 80, 100)  # Oldest complete week to newest
DEMO6 = "DEMO-Class-6"
DEMO4 = "DEMO-Class-4"
TEACHER6 = "demo_teacher6"
TEACHER4 = "demo_teacher4"
ADMIN = "demo_admin"
SUBJECT_MATH = "\u6570\u5b66"
SUBJECT_ENGLISH = "\u82f1\u8bed"
SUBJECT_CS = "\u8ba1\u7b97\u673a"


@dataclass(frozen=True)
class SeedSession:
    username: str
    task_title: str
    subject: str
    local_day: date
    start_hour: int
    minutes: int
    rating: int = 5


def four_full_weeks(today: date) -> list[date]:
    """Monday dates, oldest -> newest, excluding the currently open week."""
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(weeks=4 - i) for i in range(4)]


def make_plans(today: date) -> list[SeedSession]:
    plans: list[SeedSession] = []
    for monday, total in zip(four_full_weeks(today), WEEKLY_MINUTES):
        half = total // 2
        plans.extend([
            SeedSession("demo6_s01", "[DEMO] weekly mathematics", SUBJECT_MATH,
                        monday, 9, half),
            SeedSession("demo6_s01", "[DEMO] weekly english", SUBJECT_ENGLISH,
                        monday + timedelta(days=3), 9, total - half),
        ])

    # Two 25-minute maths sessions on the same date, ratio=100% for demo6_s02.
    plans.extend([
        SeedSession("demo6_s02", "[DEMO] two mathematics sessions", SUBJECT_MATH,
                    today, 8, 25),
        SeedSession("demo6_s02", "[DEMO] two mathematics sessions", SUBJECT_MATH,
                    today, 10, 25),
    ])

    # Seven consecutive local calendar days, one record/day, for badge tests.
    for days_ago in range(6, -1, -1):
        plans.append(SeedSession(
            "demo6_s03", "[DEMO] seven-day streak", SUBJECT_CS,
            today - timedelta(days=days_ago), 0, 10,
        ))
    return plans


def local_as_utc_naive(day: date, hour: int) -> datetime:
    local_dt = datetime.combine(day, time(hour, 0), tzinfo=LOCAL_TZ)
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


def self_test() -> None:
    today = datetime.now(LOCAL_TZ).date()
    weeks = four_full_weeks(today)
    plans = make_plans(today)
    assert len(weeks) == 4
    assert len(plans) == 17
    assert weeks[-1] + timedelta(days=7) == today - timedelta(days=today.weekday())
    for monday, expected in zip(weeks, WEEKLY_MINUTES):
        total = sum(p.minutes for p in plans if p.username == "demo6_s01"
                    and monday <= p.local_day < monday + timedelta(days=7))
        assert total == expected, (monday, total, expected)
    same_day_math = [p for p in plans if p.username == "demo6_s02"]
    assert len(same_day_math) == 2 and sum(p.minutes for p in same_day_math) == 50
    seven_dates = [p.local_day for p in plans if p.username == "demo6_s03"]
    assert seven_dates == [today - timedelta(days=i) for i in range(6, -1, -1)]
    print("SELF-TEST PASS")
    print("Business date:", today.isoformat(), "(Asia/Shanghai)")
    for monday, minutes in zip(weeks, WEEKLY_MINUTES):
        print(f"  Full week {monday} : {minutes} minutes")
    print("Forecast (four complete weeks):", sum(WEEKLY_MINUTES) // 4)
    print("Mathematics two-session total: 50; streak days: 7")


def get_id(cursor, table: str, key: str, value: object) -> int | None:
    # Identifiers come ONLY from internal hard-coded calls, not from CLI input.
    assert (table, key) in {
        ("classes", "class_name"), ("users", "username"),
        ("subjects", "subject_name"),
    }
    cursor.execute(f"SELECT id FROM {table} WHERE {key} = %s", (value,))
    row = cursor.fetchone()
    return int(row[0]) if row else None


def ensure_class(cursor, name: str) -> int:
    item_id = get_id(cursor, "classes", "class_name", name)
    if item_id is not None:
        return item_id
    cursor.execute("INSERT INTO classes (class_name) VALUES (%s)", (name,))
    return int(cursor.lastrowid)


def ensure_subject(cursor, name: str) -> int:
    item_id = get_id(cursor, "subjects", "subject_name", name)
    if item_id is not None:
        cursor.execute("UPDATE subjects SET enabled=TRUE WHERE id=%s", (item_id,))
        return item_id
    cursor.execute("INSERT INTO subjects (subject_name, enabled) VALUES (%s, TRUE)", (name,))
    return int(cursor.lastrowid)


def ensure_user(cursor, *, username: str, role: str,
                class_id: int | None, alias: str | None,
                password_hash: str) -> int:
    item_id = get_id(cursor, "users", "username", username)
    if item_id is not None:
        cursor.execute(
            """UPDATE users SET password_hash=%s, role=%s, class_id=%s,
               alias=%s, is_active=TRUE WHERE id=%s""",
            (password_hash, role, class_id, alias, item_id),
        )
        return item_id
    cursor.execute(
        """INSERT INTO users (username, password_hash, role, class_id, alias, is_active)
           VALUES (%s, %s, %s, %s, %s, TRUE)""",
        (username, password_hash, role, class_id, alias),
    )
    return int(cursor.lastrowid)


def ensure_task(cursor, student_id: int, subject_id: int, title: str) -> int:
    cursor.execute(
        "SELECT id FROM tasks WHERE student_id=%s AND title=%s ORDER BY id LIMIT 1",
        (student_id, title),
    )
    row = cursor.fetchone()
    if row:
        item_id = int(row[0])
        cursor.execute(
            "UPDATE tasks SET subject_id=%s, status='done' WHERE id=%s",
            (subject_id, item_id),
        )
        return item_id
    cursor.execute(
        """INSERT INTO tasks (student_id, subject_id, title, status)
           VALUES (%s, %s, %s, 'done')""",
        (student_id, subject_id, title),
    )
    return int(cursor.lastrowid)


def replace_sessions_for_demo_task(cursor, task_id: int) -> None:
    # Only project-owned tasks bearing the [DEMO] prefix are passed here.
    cursor.execute("SELECT title FROM tasks WHERE id=%s", (task_id,))
    row = cursor.fetchone()
    if not row or not row[0].startswith("[DEMO] "):
        raise ValueError("Refusing to replace sessions of a non-DEMO task")
    cursor.execute(
        """DELETE sr FROM study_records AS sr
           JOIN focus_sessions AS fs ON fs.id = sr.focus_session_id
           WHERE fs.task_id=%s""",
        (task_id,),
    )
    cursor.execute("DELETE FROM focus_sessions WHERE task_id=%s", (task_id,))


def add_seed_session(cursor, plan: SeedSession, user_ids: dict[str, int],
                     task_ids: dict[tuple[str, str], int],
                     subject_ids: dict[str, int]) -> None:
    start = local_as_utc_naive(plan.local_day, plan.start_hour)
    end = start + timedelta(minutes=plan.minutes)
    student_id = user_ids[plan.username]
    task_id = task_ids[(plan.username, plan.task_title)]
    cursor.execute(
        """INSERT INTO focus_sessions
           (student_id, task_id, planned_minutes, rest_minutes,
            started_at, ended_at, status)
           VALUES (%s, %s, %s, 5, %s, %s, 'completed')""",
        (student_id, task_id, plan.minutes, start, end),
    )
    session_id = int(cursor.lastrowid)
    cursor.execute(
        """INSERT INTO study_records
           (focus_session_id, student_id, subject_id,
            started_at, ended_at, minutes, rating)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (session_id, student_id, subject_ids[plan.subject],
         start, end, plan.minutes, plan.rating),
    )


def db_connect(password: str):
    import pymysql

    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user="root", password=password,
        database=DB_NAME, charset="utf8mb4", autocommit=False,
        init_command="SET time_zone = '+00:00'",
        connect_timeout=10,
    )


def seed() -> None:
    from argon2 import PasswordHasher

    print("LOCAL DEVELOPMENT DATA ONLY. No production data should be present.")
    print("This resets only [DEMO] task sessions and demo account passwords.")
    password = getpass("MySQL root password (hidden): ")
    demo_password = getpass("Choose DEMO login password (10+ chars; hidden): ")
    confirm = getpass("Confirm DEMO login password: ")
    if len(demo_password) < 10 or demo_password != confirm:
        raise ValueError("DEMO password must have 10+ characters and match confirmation")

    conn = db_connect(password)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DATABASE()")
        if cur.fetchone()[0] != DB_NAME:
            raise ValueError("Wrong target database")
        hasher = PasswordHasher()  # Argon2id hash; works with later FastAPI login.

        class_ids = {DEMO6: ensure_class(cur, DEMO6), DEMO4: ensure_class(cur, DEMO4)}
        subject_ids = {name: ensure_subject(cur, name)
                       for name in (SUBJECT_MATH, SUBJECT_ENGLISH, SUBJECT_CS)}

        user_specs: list[tuple[str, str, int | None, str | None]] = []
        for i in range(1, 7):
            user_specs.append((f"demo6_s{i:02d}", "student", class_ids[DEMO6],
                               f"demo6_alias{i:02d}"))
        for i in range(1, 5):
            user_specs.append((f"demo4_s{i:02d}", "student", class_ids[DEMO4],
                               f"demo4_alias{i:02d}"))
        user_specs += [(TEACHER6, "teacher", None, None),
                       (TEACHER4, "teacher", None, None),
                       (ADMIN, "admin", None, None)]
        user_ids = {}
        for username, role, class_id, alias in user_specs:
            user_ids[username] = ensure_user(
                cur, username=username, role=role,
                class_id=class_id, alias=alias,
                password_hash=hasher.hash(demo_password),
            )
        cur.execute("UPDATE classes SET teacher_id=%s WHERE id=%s",
                    (user_ids[TEACHER6], class_ids[DEMO6]))
        cur.execute("UPDATE classes SET teacher_id=%s WHERE id=%s",
                    (user_ids[TEACHER4], class_ids[DEMO4]))

        # This rule is for future badge tests; no badge is awarded at seed time.
        cur.execute("SELECT id FROM badge_rules WHERE badge_code='streak_7d'")
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO badge_rules
                   (badge_code, badge_name, required_days, enabled)
                   VALUES ('streak_7d', %s, 7, TRUE)""",
                ("\u8fde\u7eed7\u5929\u5b66\u4e60",),
            )

        today = datetime.now(LOCAL_TZ).date()
        plans = make_plans(today)
        task_ids = {}
        for plan in plans:
            key = (plan.username, plan.task_title)
            if key not in task_ids:
                task_ids[key] = ensure_task(
                    cur, user_ids[plan.username], subject_ids[plan.subject],
                    plan.task_title,
                )
        for task_id in task_ids.values():
            replace_sessions_for_demo_task(cur, task_id)
        for plan in plans:
            add_seed_session(cur, plan, user_ids, task_ids, subject_ids)
        conn.commit()
        print("SEED PASS: committed successfully")
        print(f"  DEMO accounts: {len(user_specs)} (10 students, 2 teachers, 1 admin)")
        print(f"  DEMO study records: {len(plans)}")
        print("  4 weekly totals: 100, 120, 80, 100; forecast: 100")
        print("  Accounts: demo6_s01, demo6_s02, demo6_s03, demo_teacher6, demo_admin ...")
        print("  Run: python scripts/verify_seed.py")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Project 20 local demo data")
    parser.add_argument("--self-test", action="store_true", help="Test dates without DB")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        seed()
