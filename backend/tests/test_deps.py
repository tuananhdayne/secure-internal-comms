import pytest
from fastapi import HTTPException
from app.db.session import engine, SessionLocal, Base
from app.models.identified import User
from app.core.security import create_access_token
from app.api.deps import get_current_user, require_role


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_get_current_user_valid_token():
    db = SessionLocal()
    try:
        user = User(
            employee_code="NV_DEPS_01",
            password_hash="hash",
            full_name="Nguyễn Văn Deps",
            department="IT",
            role="EMPLOYEE",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(subject=str(user.id), role=user.role)
        current_user = get_current_user(token=token, db=db)
        assert current_user.id == user.id
        assert current_user.employee_code == "NV_DEPS_01"
    finally:
        db.close()


def test_get_current_user_invalid_token():
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="invalid.token.here", db=db)
        assert exc_info.value.status_code == 401
    finally:
        db.close()


def test_require_role_authorized_and_forbidden():
    db = SessionLocal()
    try:
        user = User(
            employee_code="NV_DEPS_02",
            password_hash="hash",
            full_name="Nguyễn Văn Employee",
            department="IT",
            role="EMPLOYEE",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Kiểm tra vai trò hợp lệ
        checker_emp = require_role(["EMPLOYEE"])
        res_user = checker_emp(current_user=user)
        assert res_user.id == user.id

        # Kiểm tra vai trò bị từ chối (403)
        checker_officer = require_role(["COMPLIANCE_OFFICER"])
        with pytest.raises(HTTPException) as exc_info:
            checker_officer(current_user=user)
        assert exc_info.value.status_code == 403
    finally:
        db.close()
