"""Ghi nhật ký thao tác đặc quyền (bảng audit_logs). Xem docstring của models.identified.AuditLog."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.identified import AuditLog, User

logger = logging.getLogger(__name__)


class Action:
    WEB_LOGIN = "web.login"
    USER_CREATE = "user.create"
    USER_LOCK = "user.lock"
    USER_UNLOCK = "user.unlock"
    POST_CREATE = "post.create"
    POST_DELETE = "post.delete"
    CASE_VIEW = "case.view"
    CASE_STATUS = "case.status"
    CASE_REPLY = "case.reply"
    EVIDENCE_DOWNLOAD = "evidence.download"
    ROLE_CHANGE = "role.change"        # lệnh máy chủ scripts/manage_roles.py
    ACCOUNT_CREATE = "account.create"  # lệnh máy chủ
    PASSWORD_RESET = "password.reset"  # lệnh máy chủ

    LABELS = {
        WEB_LOGIN: "Đăng nhập cổng web",
        USER_CREATE: "Tạo tài khoản",
        USER_LOCK: "Khóa tài khoản",
        USER_UNLOCK: "Mở khóa tài khoản",
        POST_CREATE: "Đăng bài",
        POST_DELETE: "Xóa bài",
        CASE_VIEW: "Mở hồ sơ tố giác",
        CASE_STATUS: "Đổi trạng thái hồ sơ",
        CASE_REPLY: "Gửi phản hồi cho người tố giác",
        EVIDENCE_DOWNLOAD: "Xem / tải bằng chứng",
        ROLE_CHANGE: "Đổi vai trò (máy chủ)",
        ACCOUNT_CREATE: "Tạo tài khoản đặc quyền (máy chủ)",
        PASSWORD_RESET: "Đặt lại mật khẩu (máy chủ)",
    }


def record(db: Session, actor: Optional[User], action: str, target: str = "", detail: str = "",
           *, actor_code: str = "", actor_role: str = "") -> None:
    """Ghi một dòng nhật ký và commit. Lỗi ghi nhật ký không làm hỏng thao tác chính (chỉ log cảnh báo)."""
    try:
        db.add(AuditLog(
            actor_id=actor.id if actor else None,
            actor_code=(actor.employee_code if actor else actor_code) or "?",
            actor_role=(actor.role if actor else actor_role) or "?",
            action=action,
            target=target[:100],
            detail=detail[:255],
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Không ghi được nhật ký thao tác: %s", action)
