"""Cấu hình log thống nhất, an toàn cho dữ liệu ẩn danh.

Mỗi dòng log có dạng:
    2026-11-18 16:40:01 INFO  [3f9c1a2b7d4e] app.services.case_crypto: ...
                               ^ request_id — cùng giá trị với header `X-Request-ID` của response
                                 và trường `request_id` trong JSON lỗi 500, nên khi người dùng báo
                                 "lỗi mã abc123" chỉ cần `grep abc123` trong log.

QUY TẮC RIÊNG TƯ (không được nới lỏng):
- Không bao giờ ghi IP client. Access log mặc định của uvicorn (ghi `IP - "METHOD /path"`) bị tắt
  vì nó làm lộ IP + thời điểm chính xác + case_token của người tố giác.
- Request tới /api/v1/anonymous KHÔNG được ghi access log; chỉ ghi khi lỗi 5xx, với đường dẫn đã
  che `case_token` (xem `mask_path`).

Mức log chỉnh bằng biến môi trường LOG_LEVEL (DEBUG, INFO, WARNING...; mặc định INFO).
"""
from __future__ import annotations

import logging
import os
import re
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_ANON_CASE_PATH = re.compile(r"^(?P<prefix>/api/v1/anonymous/cases/)[^/]+")
LOG_FORMAT = "%(asctime)s %(levelname)-5s [%(request_id)s] %(name)s: %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def mask_path(path: str) -> str:
    """Che case_token trong đường dẫn ẩn danh trước khi ghi log."""
    return _ANON_CASE_PATH.sub(r"\g<prefix>{case_token}", path)


_base_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs) -> logging.LogRecord:
    # Gắn request_id vào MỌI bản ghi (kể cả handler bên ngoài như pytest caplog, uvicorn).
    record = _base_factory(*args, **kwargs)
    record.request_id = request_id_var.get()
    return record


def setup_logging() -> None:
    """Gọi một lần khi khởi tạo app (app/main.py). Gọi lại nhiều lần vẫn an toàn."""
    logging.setLogRecordFactory(_record_factory)
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    if not any(getattr(h, "_atbm", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
        handler.addFilter(RequestIdFilter())
        handler._atbm = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level)

    # Tắt access log của uvicorn (ghi IP). Access log an toàn do middleware của app tự ghi.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
    access.disabled = True

    # Thư viện ồn ào: chỉ cảnh báo trở lên
    for noisy in ("multipart", "PIL", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
