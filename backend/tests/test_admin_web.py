import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, Base, engine
from app.models.identified import User, Post
from app.core.security import get_password_hash


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    
    # Tạo sẵn admin nếu chưa có
    admin = db.query(User).filter(User.employee_code == "AD001").first()
    if not admin:
        admin = User(
            employee_code="AD001",
            full_name="Quản Trị Viên",
            password_hash=get_password_hash("AdminPass123@"),
            role="SYSTEM_ADMIN",
            department="Khối Quản trị",
            is_active=True
        )
        db.add(admin)
    else:
        admin.password_hash = get_password_hash("AdminPass123@")
        admin.is_active = True
    db.commit()
    
    # Tạo nhân viên thường
    emp = db.query(User).filter(User.employee_code == "EMP_WEB_01").first()
    if not emp:
        emp = User(
            employee_code="EMP_WEB_01",
            full_name="Nhân viên Web Test",
            password_hash=get_password_hash("EmpPass123@"),
            role="EMPLOYEE",
            department="Ban Kế toán",
            is_active=True
        )
        db.add(emp)
        db.commit()
    
    db.close()
    
    with TestClient(app) as test_client:
        yield test_client


def test_admin_login_page_renders(client: TestClient):
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert "Đăng nhập Quản trị viên" in response.text or "Admin" in response.text


def test_admin_login_and_dashboard_access(client: TestClient):
    # Đăng nhập sai
    bad_login = client.post(
        "/admin/login",
        data={"employee_code": "AD001", "password": "WrongPassword"},
        follow_redirects=False
    )
    assert bad_login.status_code == 200  # Trả về form báo lỗi
    assert "không chính xác" in bad_login.text or "Lỗi" in bad_login.text

    # Đăng nhập đúng
    good_login = client.post(
        "/admin/login",
        data={"employee_code": "AD001", "password": "AdminPass123@"},
        follow_redirects=False
    )
    assert good_login.status_code in [302, 303]
    assert good_login.headers["location"] == "/admin/dashboard"
    
    # Kiểm tra cookie
    cookie = good_login.cookies.get("admin_token")
    assert cookie is not None

    # Truy cập dashboard có cookie
    dash_resp = client.get("/admin/dashboard", cookies={"admin_token": cookie})
    assert dash_resp.status_code == 200
    assert "Quản Trị" in dash_resp.text or "Dashboard" in dash_resp.text


def test_admin_toggle_user_status(client: TestClient):
    # Lấy cookie admin
    login_resp = client.post(
        "/admin/login",
        data={"employee_code": "AD001", "password": "AdminPass123@"}
    )
    admin_cookie = login_resp.cookies.get("admin_token")

    db: Session = SessionLocal()
    target_user = db.query(User).filter(User.employee_code == "EMP_WEB_01").first()
    assert target_user is not None
    original_status = target_user.is_active
    user_id = target_user.id
    db.close()

    # Toggle status
    toggle_resp = client.post(
        f"/admin/users/toggle/{user_id}",
        cookies={"admin_token": admin_cookie},
        follow_redirects=False
    )
    assert toggle_resp.status_code in [302, 303]

    db = SessionLocal()
    updated_user = db.query(User).filter(User.id == user_id).first()
    assert updated_user.is_active != original_status
    db.close()


def test_admin_create_post(client: TestClient):
    login_resp = client.post(
        "/admin/login",
        data={"employee_code": "AD001", "password": "AdminPass123@"}
    )
    admin_cookie = login_resp.cookies.get("admin_token")

    # Tạo bài viết mới từ Web
    create_resp = client.post(
        "/admin/posts/create",
        data={
            "title": "Thông báo bảo trì hệ thống máy chủ nội bộ",
            "content": "Toàn bộ hệ thống sẽ bảo trì từ 22h00 đêm nay.",
            "is_pinned": "true"
        },
        cookies={"admin_token": admin_cookie},
        follow_redirects=False
    )
    assert create_resp.status_code in [302, 303]

    # Kiểm tra bài viết đã có trong DB
    db: Session = SessionLocal()
    new_post = db.query(Post).filter(Post.title == "Thông báo bảo trì hệ thống máy chủ nội bộ").first()
    assert new_post is not None
    assert new_post.is_pinned is True
    db.close()
