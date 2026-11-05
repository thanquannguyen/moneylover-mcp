"""Unit tests for scripts/refresh_token.py (mocked HTTP, no network)."""

import base64
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import refresh_token


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def make_urlopen(calls):
    def urlopen(req, timeout=30):
        calls.append(req.full_url)
        if req.full_url.endswith("/user/login-url"):
            return FakeResponse(
                {"data": {"request_token": "req-1", "login_url": "https://x/login?client=cli-1"}}
            )
        if req.full_url.endswith("/token"):
            assert req.headers["Authorization"] == "Bearer req-1"
            assert req.headers["Client"] == "cli-1"
            body = req.data.decode("utf-8")
            assert "email=test%40example.com" in body
            assert "password=" in body
            return FakeResponse({"access_token": "tok-123"})
        if req.full_url.endswith("/wallet/list"):
            assert req.headers["Authorization"] == "AuthJWT tok-123"
            return FakeResponse({"error": 0, "data": {"wallets": [{"name": "A"}, {"name": "B"}]}})
        raise AssertionError(req.full_url)

    return urlopen


class RefreshTokenTest(unittest.TestCase):
    def test_full_flow_caches_token_with_0600(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(refresh_token, "CACHE_DIR", Path(tmp)), mock.patch(
                "urllib.request.urlopen", make_urlopen(calls)
            ), mock.patch("getpass.getpass", return_value="secret"):
                with mock.patch.object(sys, "argv", ["refresh_token.py", "--email", "test@example.com"]):
                    self.assertEqual(refresh_token.main(), 0)
            name = base64.urlsafe_b64encode(b"test@example.com").rstrip(b"=").decode("ascii")
            path = Path(tmp) / f"{name}.json"
            self.assertTrue(path.exists())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            data = json.loads(path.read_text())
            self.assertEqual(data["token"], "tok-123")
            self.assertIn("updatedAt", data)
            self.assertNotIn("secret", path.read_text())
        self.assertEqual(
            calls,
            [
                "https://web.moneylover.me/api/user/login-url",
                "https://oauth.moneylover.me/token",
                "https://web.moneylover.me/api/wallet/list",
            ],
        )

    def test_token_failure_caches_nothing(self):
        def failing(req, timeout=30):
            raise RuntimeError("boom")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(refresh_token, "CACHE_DIR", Path(tmp)), mock.patch(
                "urllib.request.urlopen", failing
            ), mock.patch("getpass.getpass", return_value="secret"):
                with mock.patch.object(sys, "argv", ["refresh_token.py", "--email", "test@example.com"]):
                    self.assertEqual(refresh_token.main(), 1)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
