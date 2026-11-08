import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import engine, SessionLocal, Base
from app.models.identified import User, Post
from app.core.security import get_password_hash, create_access_token
from app.api.v1.posts import router as posts_router

app = FastAPI()
app.include_router(posts_router, prefix="/api/v1/posts")
client = TestClient(app)

employee_token = ""
admin_token = ""


def setup_module(module):
    global employee_token, admin_token
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    emp = User(
        employee_code="NV_POST_TEST",
        password_hash=get_password_hash("pass123"),
        full_name="Nhân viên Test",
        department="Kỹ thuật",
        role="EMPLOYEE"
    )
    admin = User(
        employee_code="AD_POST_TEST",
        password_hash=get_password_hash("pass123"),
        full_name="Admin Post Test",
        department="IT",
        role="SYSTEM_ADMIN"
    )
    db.add(emp)
    db.add(admin)
    db.commit()
    db.refresh(emp)
    db.refresh(admin)

    employee_token = create_access_token(subject=str(emp.id), role=emp.role)
    admin_token = create_access_token(subject=str(admin.id), role=admin.role)
    db.close()


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_employee_cannot_create_post():
    response = client.post(
        "/api/v1/posts",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"title": "Bai viet unauthorized", "content": "Noi dung"}
    )
    assert response.status_code == 403


def test_admin_can_create_post_and_list():
    # Admin đăng bài
    response = client.post(
        "/api/v1/posts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": "Thông báo nội bộ quan trọng", "content": "Nội dung thông báo", "category": "ANNOUNCEMENT", "is_pinned": True}
    )
    assert response.status_code == 201
    post_data = response.json()
    post_id = post_data["id"]
    assert post_data["title"] == "Thông báo nội bộ quan trọng"
    assert post_data["is_pinned"] is True

    # Employee xem danh sách
    list_resp = client.get(
        "/api/v1/posts",
        headers={"Authorization": f"Bearer {employee_token}"}
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Employee bình luận
    comment_resp = client.post(
        f"/api/v1/posts/{post_id}/comments",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"content": "Tôi đã đọc và ghi nhận thông báo."}
    )
    assert comment_resp.status_code == 201
    assert comment_resp.json()["content"] == "Tôi đã đọc và ghi nhận thông báo."

    # Xem chi tiết bài viết kèm bình luận
    detail_resp = client.get(
        f"/api/v1/posts/{post_id}",
        headers={"Authorization": f"Bearer {employee_token}"}
    )
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["comments"]) == 1
