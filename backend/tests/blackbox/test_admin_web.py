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

    # Tạo cán bộ thanh tra
    officer = db.query(User).filter(User.employee_code == "TT001").first()
    if not officer:
        officer = User(
            employee_code="TT001",
            full_name="Lê Thanh Tra",
            password_hash=get_password_hash("OfficerPass123@"),
            role="COMPLIANCE_OFFICER",
            department="Ban Thanh tra & Tuân thủ",
            is_active=True
        )
        db.add(officer)
    else:
        officer.password_hash = get_password_hash("OfficerPass123@")
        officer.is_active = True
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


def test_system_admin_forbidden_from_compliance_cases(client: TestClient):
    """Kiểm tra SYSTEM_ADMIN bị chặn nghiêm ngặt không được can thiệp vào các vụ việc thanh tra."""
    login_resp = client.post(
        "/admin/login",
        data={"employee_code": "AD001", "password": "AdminPass123@"}
    )
    admin_cookie = login_resp.cookies.get("admin_token")

    # 1. Admin vào /admin/cases -> Bị chuyển hướng về dashboard
    resp = client.get("/admin/cases", cookies={"admin_token": admin_cookie}, follow_redirects=False)
    assert resp.status_code in [302, 303]
    assert resp.headers["location"] == "/admin/dashboard"

    # 2. Admin thử giải mã hồ sơ -> 403 Forbidden
    resp = client.get("/admin/cases/1/decrypt", cookies={"admin_token": admin_cookie})
    assert resp.status_code == 403
    assert "Truy cập bị từ chối" in resp.json()["error"]

    # 3. Admin thử cập nhật trạng thái hồ sơ -> 403 Forbidden
    resp = client.post(
        "/admin/cases/1/status",
        data={"new_status": "INVESTIGATING"},
        cookies={"admin_token": admin_cookie}
    )
    assert resp.status_code == 403
    assert "Truy cập bị từ chối" in resp.json()["error"]

    # 4. Admin thử gửi tin nhắn điều tra -> 403 Forbidden
    resp = client.post(
        "/admin/cases/1/reply",
        data={"message": "Admin can thiệp trái phép"},
        cookies={"admin_token": admin_cookie}
    )
    assert resp.status_code == 403
    assert "Truy cập bị từ chối" in resp.json()["error"]


def test_compliance_officer_web_portal_access_and_actions(client: TestClient):
    """Kiểm tra Cán bộ Thanh tra đăng nhập, bị chặn quản lý user, và thụ lý/phản hồi E2EE hồ sơ thành công."""
    from datetime import datetime, timezone
    from app.models.anonymous import WhistleCase
    from app.crypto.key_manager import key_manager
    from app.crypto.ecies import ecies_encrypt

    login_resp = client.post(
        "/admin/login",
        data={"employee_code": "TT001", "password": "OfficerPass123@"},
        follow_redirects=False
    )
    assert login_resp.status_code in [302, 303]
    assert login_resp.headers["location"] == "/admin/cases"
    officer_cookie = login_resp.cookies.get("admin_token")

    # 1. Officer bị chặn không được tạo hoặc khóa user của Admin
    forbidden_create = client.post(
        "/admin/users/create",
        data={
            "employee_code": "HACK01",
            "full_name": "Hacker",
            "department": "IT",
            "role": "SYSTEM_ADMIN",
            "password": "pass"
        },
        cookies={"admin_token": officer_cookie}
    )
    assert forbidden_create.status_code == 403

    # 2. Vào trang danh sách hồ sơ
    cases_resp = client.get("/admin/cases", cookies={"admin_token": officer_cookie})
    assert cases_resp.status_code == 200
    assert "Cổng Thanh Tra" in cases_resp.text or "cases" in cases_resp.text

    # 3. Tạo một hồ sơ mã hóa ECIES thật để kiểm thử giải mã và phản hồi E2EE
    db: Session = SessionLocal()
    enc_payload = ecies_encrypt(
        key_manager.ec_public_key_hex,
        "Tiêu đề mật|||Nội dung tố giác chi tiết".encode("utf-8")
    )
    test_case = WhistleCase(
        case_token="CASE-WEB-TEST-001",
        category="THAM_NHUNG",
        encrypted_title=enc_payload["ciphertext"][:32],
        encrypted_description=enc_payload["ciphertext"],
        payload_ephemeral_pub=enc_payload["ephemeral_public_key"],
        payload_iv=enc_payload["iv"],
        payload_auth_tag=enc_payload["auth_tag"],
        unblinded_signature="0xabc123",
        case_public_key=key_manager.ec_public_key_hex,
        status="PENDING",
        created_bucket=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    cid = test_case.id
    db.close()

    # 4. Officer cập nhật trạng thái và gửi phản hồi E2EE
    status_resp = client.post(
        f"/admin/cases/{cid}/status",
        data={"new_status": "INVESTIGATING"},
        cookies={"admin_token": officer_cookie},
        follow_redirects=False
    )
    assert status_resp.status_code in [302, 303]

    reply_resp = client.post(
        f"/admin/cases/{cid}/reply",
        data={"message": "Phản hồi điều tra bảo mật E2EE"},
        cookies={"admin_token": officer_cookie},
        follow_redirects=False
    )
    assert reply_resp.status_code in [302, 303]

    # 5. Officer giải mã lại hồ sơ & lịch sử tin nhắn trên Web
    dec_resp = client.get(f"/admin/cases/{cid}/decrypt", cookies={"admin_token": officer_cookie})
    assert dec_resp.status_code == 200
    dec_json = dec_resp.json()
    assert dec_json["title"] == "Tiêu đề mật"
    assert dec_json["description"] == "Nội dung tố giác chi tiết"
    assert dec_json["status"] == "INVESTIGATING"
    assert any(m["content"] == "Phản hồi điều tra bảo mật E2EE" for m in dec_json["messages"])

    # 6. Kiểm tra API nặc danh KHÔNG làm lộ bản rõ trong digital_signature
    anon_resp = client.get("/api/v1/anonymous/cases/CASE-WEB-TEST-001")
    assert anon_resp.status_code == 200
    anon_messages = anon_resp.json()["messages"]
    assert len(anon_messages) >= 1
    for m in anon_messages:
        assert "Phản hồi điều tra bảo mật E2EE" not in m["digital_signature"]
        assert m["digital_signature"] == "OFFICER_P256_VERIFIED_SIGNATURE"
