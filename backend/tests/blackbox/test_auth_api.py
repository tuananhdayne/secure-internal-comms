import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import engine, SessionLocal, Base
from app.models.identified import User
from app.core.security import get_password_hash
from app.api.v1.auth import router as auth_router


app = FastAPI()
app.include_router(auth_router, prefix="/api/v1/auth")
client = TestClient(app)


def setup_module(module):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Tạo user test
    user = User(
        employee_code="NV_LOGIN_TEST",
        password_hash=get_password_hash("password123"),
        full_name="Nguyễn Văn Login",
        department="IT",
        role="EMPLOYEE",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.close()


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_login_success():
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "NV_LOGIN_TEST", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "NV_LOGIN_TEST", "password": "wrongpassword"}
    )
    assert response.status_code == 400
    assert "không chính xác" in response.json()["detail"]


def test_get_current_user_profile():
    # Login trước
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "NV_LOGIN_TEST", "password": "password123"}
    )
    token = login_resp.json()["access_token"]

    # Gọi /me
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    user_data = me_resp.json()
    assert user_data["employee_code"] == "NV_LOGIN_TEST"
    assert user_data["full_name"] == "Nguyễn Văn Login"
    assert user_data["role"] == "EMPLOYEE"
