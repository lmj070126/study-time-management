
import json
import unittest
from getpass import getpass
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE_URL = "http://127.0.0.1:8000"

ACCOUNTS = {
    "student": "demo6_s01",
    "teacher": "demo_teacher6",
    "admin": "demo_admin",
}

ENDPOINTS = {
    "student": "/api/auth/student-check",
    "teacher": "/api/auth/teacher-check",
    "admin": "/api/auth/admin-check",
}


def api_request(method, path, payload=None, token=None):
    headers = {"Accept": "application/json"}
    body = None

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(
        BASE_URL + path,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(
                response.read().decode("utf-8")
            )
    except HTTPError as error:
        try:
            return error.code, json.loads(
                error.read().decode("utf-8")
            )
        finally:
           error.close()

class TestAuthIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        demo_password = getpass(
            "请输入演示账号密码（不显示）："
        )
        cls.tokens = {}

        for role, username in ACCOUNTS.items():
            code, result = api_request(
                "POST",
                "/api/auth/login",
                {
                    "username": username,
                    "password": demo_password,
                },
            )

            if code != 200 or result.get("role") != role:
                raise AssertionError(
                    f"{role} 登录失败，HTTP {code}"
                )

            cls.tokens[role] = result["access_token"]

    def test_role_matrix(self):
        """测试三角色九种访问组合"""
        for login_role, token in self.tokens.items():
            for target_role, path in ENDPOINTS.items():
                expected = (
                    200 if login_role == target_role else 403
                )

                with self.subTest(
                    login_role=login_role,
                    target_role=target_role,
                ):
                    code, _ = api_request(
                        "GET", path, token=token
                    )
                    self.assertEqual(code, expected)

    def test_current_user(self):
        """测试JWT是否正确识别用户"""
        for role, token in self.tokens.items():
            with self.subTest(role=role):
                code, data = api_request(
                    "GET",
                    "/api/auth/me",
                    token=token,
                )
                self.assertEqual(code, 200)
                self.assertEqual(data["role"], role)
                self.assertEqual(
                    data["username"], ACCOUNTS[role]
                )

    def test_wrong_password(self):
        """错误密码应返回401"""
        code, _ = api_request(
            "POST",
            "/api/auth/login",
            {
                "username": "demo6_s01",
                "password": "definitely-wrong-password",
            },
        )
        self.assertEqual(code, 401)

    def test_no_token(self):
        """未登录访问应返回401"""
        code, _ = api_request(
            "GET", "/api/auth/me"
        )
        self.assertEqual(code, 401)

    def test_invalid_token(self):
        """伪造的JWT应返回401"""
        code, _ = api_request(
            "GET",
            "/api/auth/me",
            token="invalid.jwt.token",
        )
        self.assertEqual(code, 401)


if __name__ == "__main__":
    unittest.main()
