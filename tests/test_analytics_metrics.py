"""Fast, offline, deterministic analytics calculations tests (no database)."""

import unittest
from datetime import date, datetime
from backend.app.analytics_metrics import build_overview, local_study_date


class AnalyticsMathTests(unittest.TestCase):
    def test_local_day_crosses_utc_midnight(self):
        self.assertEqual(
            local_study_date(datetime(2026, 11, 26, 16, 30)),
            date(2026, 11, 27),
        )

    def test_weekly_rollup_and_streak(self):
        overview = build_overview(
            today_local=date(2026, 11, 27),
            weekly_records=[
                {
                    "subject_id": 1, "subject_name": "数学",
                    "started_at": datetime(2026, 11, 26, 16, 30),
                    "minutes": 25, "rating": 5,
                },
                {
                    "subject_id": 2, "subject_name": "英语",
                    "started_at": datetime(2026, 11, 25, 16, 30),
                    "minutes": 50, "rating": 3,
                },
            ],
            history_days=[date(2026, 11, 25), date(2026, 11, 26), date(2026, 11, 27)],
            task_total=4,
            task_done=3,
        )
        stats = overview["summary"]
        self.assertEqual(stats["today_minutes"], 25)
        self.assertEqual(stats["week_minutes"], 75)
        self.assertEqual(stats["week_sessions"], 2)
        self.assertEqual(stats["week_avg_rating"], 4.0)
        self.assertEqual(stats["task_completion_rate"], 75.0)
        self.assertEqual(stats["streak_days"], 3)
        self.assertEqual(len(overview["daily"]), 7)
        self.assertEqual(sum(s["minutes"] for s in overview["subjects"]), 75)

    def test_no_records_no_task_division_by_zero(self):
        overview = build_overview(
            today_local=date(2026, 11, 27),
            weekly_records=[], history_days=[], task_total=0, task_done=0,
        )
        self.assertEqual(overview["summary"]["week_minutes"], 0)
        self.assertEqual(overview["summary"]["task_completion_rate"], 0)
        self.assertIsNone(overview["summary"]["week_avg_rating"])
        self.assertEqual(overview["summary"]["streak_days"], 0)

    def test_streak_can_end_yesterday(self):
        overview = build_overview(
            today_local=date(2026, 11, 27),
            weekly_records=[],
            history_days=[date(2026, 11, 25), date(2026, 11, 26)],
            task_total=2, task_done=0,
        )
        self.assertEqual(overview["summary"]["streak_days"], 2)


if __name__ == "__main__":
    unittest.main()
