"""Chống dò mật khẩu (brute-force / credential stuffing) cho luồng đăng nhập định danh.

Đếm số lần đăng nhập sai theo MÃ NHÂN VIÊN trong một cửa sổ thời gian; vượt ngưỡng thì tạm khóa
tài khoản đó vài phút. Chỉ áp dụng cho luồng định danh (API /auth/login và /admin/login) — không
dùng IP và không đụng tới luồng ẩn danh.

Trạng thái lưu trong bảng `login_attempts` (models.identified.LoginAttempt): giữ nguyên khi khởi động
lại server và dùng chung khi chạy nhiều worker / nhiều máy trỏ cùng CSDL.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identified import LoginAttempt

logger = logging.getLogger("app.auth")


class LoginThrottle:
    def __init__(
        self,
        max_failures: int,
        window_seconds: float,
        lockout_seconds: float,
        clock: Callable[[], float] = time.time,
        session_factory: Optional[Callable[[], Session]] = None,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._clock = clock
        self._session_factory = session_factory

    def _session(self) -> Session:
        if self._session_factory is None:
            from app.db.session import SessionLocal
            self._session_factory = SessionLocal
        return self._session_factory()

    @staticmethod
    def _key(employee_code: str) -> str:
        return employee_code.strip().upper()[:50]

    def retry_after(self, employee_code: str) -> int:
        """Số giây còn bị khóa (0 nếu được phép thử đăng nhập)."""
        now = self._clock()
        with self._session() as db:
            row = db.get(LoginAttempt, self._key(employee_code))
            if row is None or row.locked_until <= now:
                return 0
            return int(row.locked_until - now) + 1

    def record_failure(self, employee_code: str) -> None:
        now = self._clock()
        key = self._key(employee_code)
        with self._session() as db:
            row = db.get(LoginAttempt, key)
            if row is None:
                row = LoginAttempt(account_key=key, fail_count=0, window_start=now, locked_until=0.0)
                db.add(row)
            if now - row.window_start >= self.window_seconds:
                row.fail_count, row.window_start = 0, now
            row.fail_count += 1
            count = row.fail_count
            locked = count >= self.max_failures
            if locked:
                row.locked_until = now + self.lockout_seconds
                row.fail_count, row.window_start = 0, now
            db.commit()
        # Luồng định danh (không phải ẩn danh) -> được ghi mã tài khoản; KHÔNG ghi IP.
        # Mã do người dùng nhập: lọc ký tự lạ để không thể chèn dòng log giả (log injection).
        safe = re.sub(r"[^A-Z0-9._-]", "?", key)
        if locked:
            logger.warning("Tạm khóa đăng nhập tài khoản %s %d phút sau %d lần nhập sai",
                           safe, int(self.lockout_seconds // 60), self.max_failures)
        else:
            logger.warning("Đăng nhập sai: tài khoản %s (lần %d/%d)", safe, count, self.max_failures)

    def record_success(self, employee_code: str) -> None:
        with self._session() as db:
            db.query(LoginAttempt).filter(LoginAttempt.account_key == self._key(employee_code)).delete()
            db.commit()

    def reset(self) -> None:
        """Xóa toàn bộ bộ đếm (dùng trong kiểm thử). Tự tạo bảng nếu chưa có."""
        with self._session() as db:
            LoginAttempt.__table__.create(bind=db.get_bind(), checkfirst=True)
            db.query(LoginAttempt).delete()
            db.commit()


login_throttle = LoginThrottle(
    max_failures=settings.LOGIN_MAX_FAILURES,
    window_seconds=settings.LOGIN_WINDOW_MINUTES * 60,
    lockout_seconds=settings.LOGIN_LOCKOUT_MINUTES * 60,
)


def lockout_message(retry_after_seconds: int) -> str:
    minutes = max(1, (retry_after_seconds + 59) // 60)
    return f"Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau khoảng {minutes} phút."
