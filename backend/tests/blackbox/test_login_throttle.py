"""Chống dò mật khẩu + tắt /docs trên bản bàn giao."""
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app
from app.services.login_throttle import LoginThrottle

client = TestClient(app)


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_throttle_locks_after_max_failures_and_expires() -> None:
    clock = _Clock()
    t = LoginThrottle(max_failures=3, window_seconds=60, lockout_seconds=120, clock=clock)
    for _ in range(2):
        t.record_failure("nv001")
    assert t.retry_after("NV001") == 0
    t.record_failure(" NV001 ")  # chuẩn hóa hoa/thường + khoảng trắng
    assert t.retry_after("nv001") > 0
    clock.now += 121
    assert t.retry_after("NV001") == 0


def test_throttle_failures_outside_window_do_not_count() -> None:
    clock = _Clock()
    t = LoginThrottle(max_failures=3, window_seconds=60, lockout_seconds=120, clock=clock)
    t.record_failure("NV001"); t.record_failure("NV001")
    clock.now += 61
    t.record_failure("NV001")
    assert t.retry_after("NV001") == 0


def test_success_resets_counter() -> None:
    clock = _Clock()
    t = LoginThrottle(max_failures=2, window_seconds=60, lockout_seconds=120, clock=clock)
    t.record_failure("NV001")
    t.record_success("NV001")
    t.record_failure("NV001")
    assert t.retry_after("NV001") == 0


def _api_login(code: str, password: str):
    return client.post("/api/v1/auth/login", data={"username": code, "password": password})


def test_api_login_locked_even_with_correct_password() -> None:
    for _ in range(settings.LOGIN_MAX_FAILURES):
        assert _api_login("NV002", "sai-mat-khau").status_code == 400
    locked = _api_login("NV002", "employee123")
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0
    # Tài khoản khác không bị ảnh hưởng
    assert _api_login("NV001", "employee123").status_code == 200


def test_web_login_lockout() -> None:
    for _ in range(settings.LOGIN_MAX_FAILURES):
        client.post("/admin/login", data={"employee_code": "TT001", "password": "sai"}, follow_redirects=False)
    resp = client.post("/admin/login", data={"employee_code": "TT001", "password": "officer123"}, follow_redirects=False)
    assert resp.status_code == 429
    assert "sai quá nhiều lần" in resp.text
    assert "admin_token" not in resp.cookies


def test_api_docs_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_API_DOCS", raising=False)
    assert Settings(_env_file=None).ENABLE_API_DOCS is False
