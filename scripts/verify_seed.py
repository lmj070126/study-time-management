"""Verify Project 20 local demo seed after running seed_demo.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from getpass import getpass
from zoneinfo import ZoneInfo

import pymysql

from seed_demo import DB_NAME, LOCAL_TZ, WEEKLY_MINUTES, DEMO6, DEMO4, four_full_weeks


def main() -> None:
    db_password = getpass("MySQL root password (hidden): ")
    conn = pymysql.connect(
        host="127.0.0.1", port=3306, user="root", password=db_password,
        database=DB_NAME, charset="utf8mb4", autocommit=True,
        init_command="SET time_zone = '+00:00'",
    )
    try:
        with conn.cursor() as c:
            c.execute("""SELECT cl.class_name, COUNT(u.id)
                FROM classes cl JOIN users u ON u.class_id=cl.id AND u.role='student'
                WHERE cl.class_name IN (%s,%s)
                GROUP BY cl.class_name""", (DEMO6, DEMO4))
            sizes = {name: int(n) for name, n in c.fetchall()}
            print("Class student counts:", sizes)
            assert sizes == {DEMO6: 6, DEMO4: 4}, "Wrong class sizes"

            c.execute("SELECT id FROM users WHERE username='demo6_s01'")
            student1 = c.fetchone()[0]
            c.execute("SELECT id FROM users WHERE username='demo6_s02'")
            student2 = c.fetchone()[0]
            c.execute("SELECT id FROM users WHERE username='demo6_s03'")
            student3 = c.fetchone()[0]
            today = datetime.now(LOCAL_TZ).date()
            totals = []
            for monday in four_full_weeks(today):
                local_start = datetime.combine(monday, datetime.min.time(), tzinfo=LOCAL_TZ)
                start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
                end = (local_start + timedelta(weeks=1)).astimezone(timezone.utc).replace(tzinfo=None)
                c.execute("""SELECT COALESCE(SUM(minutes),0) FROM study_records
                    WHERE student_id=%s AND started_at >= %s AND started_at < %s""",
                    (student1, start, end))
                totals.append(int(c.fetchone()[0]))
            print("Four full weekly totals (oldest -> newest):", totals)
            assert tuple(totals) == WEEKLY_MINUTES, "Four-week totals mismatch"
            assert sum(totals) // 4 == 100

            c.execute("SELECT minutes, subject_id FROM study_records WHERE student_id=%s",
                      (student2,))
            two_rows = c.fetchall()
            assert len(two_rows) == 2, "Expected exactly 2 study records for demo6_s02"
            assert sum(int(row[0]) for row in two_rows) == 50
            assert len({row[1] for row in two_rows}) == 1, "Only mathematics expected"
            print("Math two 25-min sessions: PASS (50 min; 100% mathematics)")

            c.execute("SELECT started_at FROM study_records WHERE student_id=%s", (student3,))
            local_dates = sorted({v[0].replace(tzinfo=timezone.utc)
                                  .astimezone(LOCAL_TZ).date() for v in c.fetchall()})
            expected = [today - timedelta(days=i) for i in range(6, -1, -1)]
            assert local_dates == expected, "Seven-day streak mismatch"
            print("Seven consecutive local days: PASS")

            c.execute("""SELECT COUNT(*) FROM study_records sr
                JOIN focus_sessions fs ON fs.id=sr.focus_session_id
                JOIN tasks t ON t.id=fs.task_id
                WHERE t.title LIKE '[DEMO]%%'""")
            count = int(c.fetchone()[0])
            print("Seeded study records:", count)
            assert count == 17, "Expected 17 DEMO study records"

            c.execute("""SELECT COUNT(*) FROM (
                SELECT focus_session_id FROM study_records
                GROUP BY focus_session_id HAVING COUNT(*)>1) AS dup""")
            assert int(c.fetchone()[0]) == 0, "Duplicate session records found"
            c.execute("SELECT COUNT(*) FROM users WHERE username LIKE 'demo6_s%%' OR username LIKE 'demo4_s%%'")
            assert int(c.fetchone()[0]) == 10, "Expected exactly 10 DEMO students"
            print("VERIFY PASS: 6+4 students, 4 full weeks, 50 math minutes, 7-day streak, no duplicates")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
