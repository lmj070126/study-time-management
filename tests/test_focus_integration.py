"""Live integration test for focus timer (creates one task and one study record).

Requires the local FastAPI server on http://127.0.0.1:8000 and demo accounts.
The test uses a one-minute focus interval and waits for real elapsed time.
"""

import json
import time
import unittest
from getpass import getpass
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"


def api(method, path, body=None, token=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as err:
        try:
            return err.code, json.loads(err.read().decode("utf-8"))
        finally:
            err.close()


class FocusIntegrationTest(unittest.TestCase):
    def test_live_one_minute_focus(self):
        pwd = getpass("Demo account password (hidden): ")
        tokens = {}
        for user in ("demo6_s01", "demo6_s02"):
            code, response = api("POST", "/api/auth/login", {
                "username": user, "password": pwd,
            })
            self.assertEqual(code, 200, f"Login failed: {user}: {response}")
            tokens[user] = response["access_token"]
        student_a, student_b = tokens["demo6_s01"], tokens["demo6_s02"]
        code, subjects = api("GET", "/api/tasks/subjects", token=student_a)
        self.assertEqual(code, 200)
        self.assertTrue(subjects, "At least one enabled subject is required")
        code, task = api("POST", "/api/tasks", {
            "subject_id": subjects[0]["id"],
            "title": "[TEST] One-minute focus workflow",
            "description": "Created by integration tests",
        }, student_a)
        self.assertEqual(code, 201, task)
        task_id = task["id"]

        code, session = api("POST", "/api/focus/start", {
            "task_id": task_id,
            "planned_minutes": 1,
            "rest_minutes": 5,
        }, student_a)
        self.assertEqual(code, 201, session)
        session_id = session["session_id"]
        self.assertEqual(session["status"], "running")

        code, _ = api("POST", "/api/focus/start", {
            "task_id": task_id, "planned_minutes": 1,
        }, student_a)
        self.assertEqual(code, 409, "Overlapping focus sessions must be blocked")
        code, _ = api("POST", f"/api/focus/{session_id}/complete", {
            "rating": 5,
        }, student_b)
        self.assertEqual(code, 404, "Other students must not complete this session")
        code, _ = api("POST", f"/api/focus/{session_id}/complete", {
            "rating": 5,
        }, student_a)
        self.assertEqual(code, 409, "Finishing before one minute should fail")

        print("Waiting 62 seconds to validate server-side elapsed time.", flush=True)
        time.sleep(62)
        code, completed = api("POST", f"/api/focus/{session_id}/complete", {
            "rating": 5,
        }, student_a)
        self.assertEqual(code, 200, completed)
        self.assertEqual(completed["minutes"], 1)
        self.assertFalse(completed["already_completed"])
        record_id = completed["id"]

        code, retry = api("POST", f"/api/focus/{session_id}/complete", {
            "rating": 1,
        }, student_a)
        self.assertEqual(code, 200, retry)
        self.assertTrue(retry["already_completed"])
        self.assertEqual(retry["id"], record_id)
        self.assertEqual(retry["rating"], 5, "First submitted rating must remain unchanged")

        code, records = api("GET", "/api/focus/records", token=student_a)
        self.assertEqual(code, 200)
        matches = [x for x in records if x["focus_session_id"] == session_id]
        self.assertEqual(len(matches), 1, "One session can create only one study record")
        self.assertEqual(matches[0]["minutes"], 1)

        code, records_b = api("GET", "/api/focus/records", token=student_b)
        self.assertEqual(code, 200)
        self.assertFalse(any(x["focus_session_id"] == session_id for x in records_b))
        code, _ = api("GET", "/api/focus/records")
        self.assertEqual(code, 401)
        print(f"PASS: session {session_id} -> record {record_id}, exactly once.")


if __name__ == "__main__":
    unittest.main()
