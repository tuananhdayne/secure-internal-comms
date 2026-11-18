"""Kiểm thử bảng phân quyền (app/core/permissions.py) ô-theo-ô trên API và Web Admin.

Mỗi tham số = (vai trò, được phép?). Nếu bảng quyền thay đổi, test này phải được cập nhật cùng.
"""
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from app.core.permissions import PRIVILEGED_ROLES, ROLE_PERMISSIONS, WEB_ASSIGNABLE_ROLES, Perm, has_permission
from app.core.security import create_access_token
from app.db import seed
from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.models.identified import Post, User

CODES = {"EMPLOYEE": "NV001", "BOARD_DIRECTOR": "GD001", "COMPLIANCE_OFFICER": "TT001", "SYSTEM_ADMIN": "AD001"}
ROLES = list(CODES)


def _tokens() -> Dict[str, str]:
    with SessionLocal() as db:
        out = {}
        for role, code in CODES.items():
            u = db.query(User).filter(User.employee_code == code).one()
            assert u.role == role
            out[role] = create_access_token(subject=str(u.id), role=u.role)
        return out


TOKENS: Dict[str, str] = {}


@pytest.fixture(scope="module", autouse=True)
def _seeded_db():
    """Các file test khác drop_all sau khi chạy -> tự tạo bảng + dữ liệu mẫu cho module này."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed.seed_database(db)
    TOKENS.update(_tokens())
    yield


def _api(role: str) -> TestClient:
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {TOKENS[role]}"
    return c


def _web(role: str) -> TestClient:
    c = TestClient(app)
    c.cookies.set("admin_token", TOKENS[role])
    return c


def _first_post_id() -> int:
    with SessionLocal() as db:
        return db.query(Post).first().id


# ---------------- Bảng quyền: các bất biến nghiệp vụ ----------------

def test_matrix_separation_of_duties() -> None:
    # Quản trị: không đọc / thống kê / gửi tố giác, không dùng app
    for perm in (Perm.CASE_MANAGE, Perm.CASE_STATS, Perm.WHISTLE_SUBMIT, Perm.APP_ACCESS):
        assert not has_permission("SYSTEM_ADMIN", perm)
    # Chỉ Thanh tra xử lý hồ sơ
    assert {r for r in ROLE_PERMISSIONS if has_permission(r, Perm.CASE_MANAGE)} == {"COMPLIANCE_OFFICER"}
    # Chỉ Quản trị quản lý nhân sự & bảng tin
    assert {r for r in ROLE_PERMISSIONS if has_permission(r, Perm.USER_MANAGE)} == {"SYSTEM_ADMIN"}
    assert {r for r in ROLE_PERMISSIONS if has_permission(r, Perm.POST_MANAGE)} == {"SYSTEM_ADMIN"}
    # Vai trò đặc quyền không bao giờ cấp được qua web
    assert not (PRIVILEGED_ROLES & WEB_ASSIGNABLE_ROLES)
    # Vai trò lạ không có quyền gì
    assert not has_permission("SUPER_HACKER", Perm.APP_ACCESS)


# ---------------- API (ứng dụng di động) ----------------

@pytest.mark.parametrize("role,allowed", [("EMPLOYEE", 1), ("BOARD_DIRECTOR", 1), ("COMPLIANCE_OFFICER", 1), ("SYSTEM_ADMIN", 0)])
def test_api_read_feed(role: str, allowed: int) -> None:
    assert _api(role).get("/api/v1/posts").status_code == (200 if allowed else 403)


@pytest.mark.parametrize("role,allowed", [("EMPLOYEE", 1), ("BOARD_DIRECTOR", 1), ("COMPLIANCE_OFFICER", 1), ("SYSTEM_ADMIN", 0)])
def test_api_comment(role: str, allowed: int) -> None:
    r = _api(role).post(f"/api/v1/posts/{_first_post_id()}/comments", json={"content": f"test quyền {role}"})
    assert r.status_code == (201 if allowed else 403)


@pytest.mark.parametrize("role,allowed", [("EMPLOYEE", 0), ("BOARD_DIRECTOR", 0), ("COMPLIANCE_OFFICER", 0), ("SYSTEM_ADMIN", 1)])
def test_api_publish_post(role: str, allowed: int) -> None:
    r = _api(role).post("/api/v1/posts", json={"title": f"Bài thử {role}", "content": "nội dung"})
    assert r.status_code == (201 if allowed else 403)


@pytest.mark.parametrize("role,allowed", [("EMPLOYEE", 1), ("BOARD_DIRECTOR", 1), ("COMPLIANCE_OFFICER", 1), ("SYSTEM_ADMIN", 0)])
def test_api_blind_sign(role: str, allowed: int) -> None:
    # Giá trị sai định dạng: người có quyền nhận 400 (không tốn lượt), người không có quyền nhận 403.
    r = _api(role).post("/api/v1/compliance/blind-sign", json={"blinded_hash": "không-phải-số"})
    assert r.status_code == (400 if allowed else 403)


@pytest.mark.parametrize("role,allowed", [("EMPLOYEE", 0), ("BOARD_DIRECTOR", 0), ("COMPLIANCE_OFFICER", 1), ("SYSTEM_ADMIN", 0)])
def test_api_officer_cases(role: str, allowed: int) -> None:
    assert _api(role).get("/api/v1/officer/cases").status_code == (200 if allowed else 403)


@pytest.mark.parametrize("code,password,expected", [
    ("NV001", "employee123", 200), ("GD001", "director123", 200), ("TT001", "officer123", 200), ("AD001", "admin123", 403),
])
def test_api_login_app_access(code: str, password: str, expected: int) -> None:
    r = TestClient(app).post("/api/v1/auth/login", data={"username": code, "password": password})
    assert r.status_code == expected, r.text


# ---------------- Web Admin ----------------

WEB_PAGES = {
    "/admin/cases": {"COMPLIANCE_OFFICER"},
    "/admin/stats": {"COMPLIANCE_OFFICER", "BOARD_DIRECTOR"},
    "/admin/dashboard": {"SYSTEM_ADMIN"},
    "/admin/users": {"SYSTEM_ADMIN"},
    "/admin/posts": {"SYSTEM_ADMIN"},
}


@pytest.mark.parametrize("path", list(WEB_PAGES))
@pytest.mark.parametrize("role", ROLES)
def test_web_pages(path: str, role: str) -> None:
    r = _web(role).get(path, follow_redirects=False)
    if role == "EMPLOYEE":
        assert r.status_code == 303 and r.headers["location"] == "/admin/login"  # không có quyền cổng web
    elif role in WEB_PAGES[path]:
        assert r.status_code == 200
    else:
        assert r.status_code == 303 and r.headers["location"] != path


def test_web_admin_cannot_grant_privileged_roles() -> None:
    web = _web("SYSTEM_ADMIN")
    for role in ("COMPLIANCE_OFFICER", "SYSTEM_ADMIN"):
        r = web.post("/admin/users/create", data={
            "employee_code": f"X_{role}", "full_name": "Thử", "department": "IT", "role": role, "password": "Password123@",
        }, follow_redirects=False)
        assert r.status_code == 403
    with SessionLocal() as db:
        assert db.query(User).filter(User.employee_code.in_(["X_COMPLIANCE_OFFICER", "X_SYSTEM_ADMIN"])).count() == 0
    ok = web.post("/admin/users/create", data={
        "employee_code": "X_BOARD", "full_name": "Thử", "department": "BGĐ", "role": "BOARD_DIRECTOR", "password": "Password123@",
    }, follow_redirects=False)
    assert ok.status_code == 303


def test_web_admin_cannot_lock_officer() -> None:
    with SessionLocal() as db:
        officer_id = db.query(User).filter(User.employee_code == "TT001").one().id
    r = _web("SYSTEM_ADMIN").post(f"/admin/users/toggle/{officer_id}", follow_redirects=False)
    assert r.status_code == 403
    with SessionLocal() as db:
        assert db.query(User).filter(User.id == officer_id).one().is_active


def test_web_board_cannot_decrypt_case() -> None:
    r = _web("BOARD_DIRECTOR").get("/admin/cases/1/decrypt")
    assert r.status_code == 403
