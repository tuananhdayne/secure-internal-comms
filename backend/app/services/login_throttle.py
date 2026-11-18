"""Chống dò mật khẩu (brute-force / credential stuffing) cho luồng đăng nhập định danh.

Đếm số lần đăng nhập sai theo MÃ NHÂN VIÊN trong một cửa sổ thời gian; vượt ngưỡng thì
tạm khóa tài khoản đó vài phút. Chỉ áp dụng cho luồng định danh (API /auth/login và
/admin/login) — không dùng IP và không đụng tới luồng ẩn danh.

Trạng thái lưu trong bộ nhớ tiến trình: đủ cho triển khai 1 tiến trình uvicorn. Nếu chạy
nhiều worker / nhiều máy cần chuyển sang kho dùng chung (Redis...).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from app.core.config import settings

logger = logging.getLogger("app.auth")


@dataclass
class _Entry:
    failures: List[float] = field(default_factory=list)
    locked_until: float = 0.0


class LoginThrottle:
    def __init__(
        self,
        max_failures: int,
        window_seconds: float,
        lockout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._clock = clock
        self._entries: Dict[str, _Entry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(employee_code: str) -> str:
        return employee_code.strip().upper()

    def retry_after(self, employee_code: str) -> int:
        """Số giây còn bị khóa (0 nếu được phép thử đăng nhập)."""
        now = self._clock()
        with self._lock:
            entry = self._entries.get(self._key(employee_code))
            if entry is None or entry.locked_until <= now:
                return 0
            return int(entry.locked_until - now) + 1

    def record_failure(self, employee_code: str) -> None:
        now = self._clock()
        key = self._key(employee_code)
        with self._lock:
            entry = self._entries.setdefault(key, _Entry())
            entry.failures = [t for t in entry.failures if now - t < self.window_seconds]
            entry.failures.append(now)
            count = len(entry.failures)
            locked = count >= self.max_failures
            if locked:
                entry.locked_until = now + self.lockout_seconds
                entry.failures.clear()
            self._prune(now)
        # Luồng định danh (không phải ẩn danh) -> được ghi mã tài khoản; KHÔNG ghi IP.
        # Mã do người dùng nhập: lọc ký tự lạ để không thể chèn dòng log giả (log injection).
        key = re.sub(r"[^A-Z0-9._-]", "?", key)
        if locked:
            logger.warning("Tạm khóa đăng nhập tài khoản %s %d phút sau %d lần nhập sai",
                           key[:50], int(self.lockout_seconds // 60), self.max_failures)
        else:
            logger.warning("Đăng nhập sai: tài khoản %s (lần %d/%d)", key[:50], count, self.max_failures)

    def record_success(self, employee_code: str) -> None:
        with self._lock:
            self._entries.pop(self._key(employee_code), None)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()

    def _prune(self, now: float) -> None:
        # Giữ bộ nhớ gọn: bỏ các mục đã hết khóa và không còn lần sai nào trong cửa sổ.
        if len(self._entries) < 1024:
            return
        stale = [
            k for k, e in self._entries.items()
            if e.locked_until <= now and not any(now - t < self.window_seconds for t in e.failures)
        ]
        for k in stale:
            del self._entries[k]


login_throttle = LoginThrottle(
    max_failures=settings.LOGIN_MAX_FAILURES,
    window_seconds=settings.LOGIN_WINDOW_MINUTES * 60,
    lockout_seconds=settings.LOGIN_LOCKOUT_MINUTES * 60,
)


def lockout_message(retry_after_seconds: int) -> str:
    minutes = max(1, (retry_after_seconds + 59) // 60)
    return f"Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau khoảng {minutes} phút."
