"""Middleware HTTP của ứng dụng (đăng ký trong app/main.py), chạy theo thứ tự:

1. Gắn request_id (header X-Request-ID cho mọi response, có trong mọi dòng log).
2. Route ẩn danh: xóa các header có thể chứa IP (X-Forwarded-For, X-Real-IP, Client-IP).
3. Gọi route. Lỗi không bắt được -> log traceback kèm request_id, trả JSON 500 có request_id.
4. Ghi access log an toàn (không IP; bỏ qua route ẩn danh trừ khi lỗi 5xx).
5. Thêm header bảo mật (nosniff, chống clickjacking, HSTS khi HTTPS, sandbox cho /uploads).
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import mask_path, request_id_var

logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.error")

ANON_PREFIX = f"{settings.API_V1_STR}/anonymous"
IP_HEADERS = {b"x-forwarded-for", b"x-real-ip", b"client-ip", b"forwarded", b"true-client-ip", b"cf-connecting-ip"}
UPLOADS_CSP = "sandbox; default-src 'none'; img-src 'self'; media-src 'self'; style-src 'unsafe-inline'"


def _apply_security_headers(request: Request, response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if request.url.path.startswith(("/admin/evidence/", f"{settings.API_V1_STR}/officer/evidence/")):
        # Tệp bằng chứng là nội dung không tin cậy: mở trực tiếp cũng không chạy được script.
        response.headers["Content-Security-Policy"] = UPLOADS_CSP


async def app_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    is_anonymous = request.url.path.startswith(ANON_PREFIX)
    if is_anonymous:
        request.scope["headers"] = [(k, v) for k, v in request.scope.get("headers", []) if k.lower() not in IP_HEADERS]

    started = time.perf_counter()
    try:
        try:
            response = await call_next(request)
        except Exception:
            error_logger.exception("Lỗi không xử lý được: %s %s", request.method, mask_path(request.url.path))
            response = JSONResponse(
                status_code=500,
                content={"detail": "Lỗi máy chủ nội bộ. Gửi mã request_id cho quản trị viên để tra log.",
                         "request_id": request_id},
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        if not is_anonymous:
            code = response.status_code
            if request.url.path.startswith("/static/"):
                level = logging.DEBUG
            elif code in (401, 403, 429):
                level = logging.WARNING
            elif code >= 500:
                level = logging.ERROR
            else:
                level = logging.INFO
            logger.log(level, "%s %s -> %s (%.1f ms)", request.method, request.url.path, code, elapsed_ms)
        elif response.status_code >= 500:
            logger.warning("%s %s -> %s", request.method, mask_path(request.url.path), response.status_code)

        response.headers["X-Request-ID"] = request_id
        _apply_security_headers(request, response)
        return response
    finally:
        request_id_var.reset(token)
