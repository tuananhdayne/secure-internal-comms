"""Bảng phân quyền DUY NHẤT của hệ thống (nguồn sự thật cho API và Web Admin).

Nguyên tắc nghiệp vụ (ISO 37002 / Chỉ thị EU 2019/1937 về bảo vệ người tố giác):
- Tách bạch nhiệm vụ: người vận hành hệ thống (Quản trị) không đọc được tố giác,
  không gửi tố giác và không tự cấp được quyền Thanh tra cho ai (kể cả chính mình).
- Biết khi cần biết: chỉ Cán bộ Thanh tra xem/xử lý nội dung hồ sơ.
- Vai trò đặc quyền (Thanh tra, Quản trị) chỉ được cấp qua lệnh trên máy chủ
  (`scripts/manage_roles.py`), không cấp qua giao diện web.

Mọi route phải kiểm tra bằng `has_permission` / `require_permission` thay vì so vai trò thủ công.
Bảng quyền được kiểm thử ô-theo-ô trong tests/blackbox/test_permissions.py.
"""
from typing import Dict, FrozenSet

from app.core.constants import Role


class Perm:
    # Ứng dụng di động (luồng định danh)
    APP_ACCESS = "app.access"              # đăng nhập app, đọc bảng tin
    FEED_COMMENT = "feed.comment"          # bình luận bài viết
    WHISTLE_SUBMIT = "whistle.submit"      # xin chữ ký mù để gửi tố giác ẩn danh
    # Cổng web
    WEB_PORTAL = "web.portal"              # đăng nhập cổng web
    CASE_MANAGE = "case.manage"            # xem nội dung, trao đổi, đổi trạng thái hồ sơ
    CASE_STATS = "case.stats"              # thống kê số lượng hồ sơ (không có nội dung)
    POST_MANAGE = "post.manage"            # đăng / ghim / xóa bảng tin
    USER_MANAGE = "user.manage"            # tạo, khóa/mở khóa tài khoản Nhân viên & Ban Giám đốc


ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    Role.EMPLOYEE: frozenset({Perm.APP_ACCESS, Perm.FEED_COMMENT, Perm.WHISTLE_SUBMIT}),
    Role.BOARD_DIRECTOR: frozenset({
        Perm.APP_ACCESS, Perm.FEED_COMMENT, Perm.WHISTLE_SUBMIT,
        Perm.WEB_PORTAL, Perm.CASE_STATS,
    }),
    Role.COMPLIANCE_OFFICER: frozenset({
        Perm.APP_ACCESS, Perm.FEED_COMMENT, Perm.WHISTLE_SUBMIT,
        Perm.WEB_PORTAL, Perm.CASE_MANAGE, Perm.CASE_STATS,
    }),
    Role.SYSTEM_ADMIN: frozenset({Perm.WEB_PORTAL, Perm.POST_MANAGE, Perm.USER_MANAGE}),
}

# Vai trò Quản trị viên được phép gán / khóa / mở khóa qua web.
WEB_ASSIGNABLE_ROLES: FrozenSet[str] = frozenset({Role.EMPLOYEE, Role.BOARD_DIRECTOR})
# Vai trò đặc quyền: chỉ cấp/thu hồi/khóa qua scripts/manage_roles.py trên máy chủ.
PRIVILEGED_ROLES: FrozenSet[str] = frozenset({Role.COMPLIANCE_OFFICER, Role.SYSTEM_ADMIN})


def _normalize(role: str) -> str:
    # Bí danh cũ trong dữ liệu
    return Role.BOARD_DIRECTOR if role == "BOARD_OF_DIRECTORS" else role


def has_permission(role: str, perm: str) -> bool:
    return perm in ROLE_PERMISSIONS.get(_normalize(role or ""), frozenset())


def roles_with(perm: str) -> FrozenSet[str]:
    return frozenset(r for r, perms in ROLE_PERMISSIONS.items() if perm in perms)
