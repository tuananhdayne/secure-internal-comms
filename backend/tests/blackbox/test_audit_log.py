"""Nhật ký thao tác: ghi đủ thao tác đặc quyền, KHÔNG ghi hoạt động của nhân viên trên app."""
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db import seed
from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.models.anonymous import WhistleCase
from app.models.identified import AuditLog, User


@pytest.fixture(scope="module", autouse=True)
def _db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed.seed_database(db)
        if not db.query(WhistleCase).filter(WhistleCase.case_token == "CASE-AUDIT-TEST").first():
            from datetime import datetime, timezone
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            pub_hex = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint).hex()
            db.add(WhistleCase(case_token="CASE-AUDIT-TEST", category="Thử", encrypted_title="aa",
                               encrypted_description="bb", payload_ephemeral_pub="04" + "11" * 64,
                               payload_iv="22" * 12, payload_auth_tag="33" * 16, case_public_key=pub_hex,
                               unblinded_signature="55", status="PENDING",
                               created_bucket=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)))
            db.commit()
    yield


def _web(code: str) -> TestClient:
    with SessionLocal() as db:
        u = db.query(User).filter(User.employee_code == code).one()
        tok = create_access_token(subject=str(u.id), role=u.role)
    c = TestClient(app)
    c.cookies.set("admin_token", tok)
    return c


def _count(**f) -> int:
    with SessionLocal() as db:
        return db.query(AuditLog).filter_by(**f).count()


def _case_id() -> int:
    with SessionLocal() as db:
        return db.query(WhistleCase).filter(WhistleCase.case_token == "CASE-AUDIT-TEST").one().id


def test_officer_case_actions_are_logged() -> None:
    cid = _case_id()
    web = _web("TT001")
    before_view = _count(action="case.view", target=f"case:{cid}")
    assert web.get(f"/admin/cases/{cid}/decrypt").status_code == 200
    assert _count(action="case.view", target=f"case:{cid}") == before_view + 1
    web.post(f"/admin/cases/{cid}/status", data={"new_status": "INVESTIGATING"}, follow_redirects=False)
    with SessionLocal() as db:
        row = db.query(AuditLog).filter_by(action="case.status", target=f"case:{cid}").order_by(AuditLog.id.desc()).first()
        assert row.actor_code == "TT001" and row.actor_role == "COMPLIANCE_OFFICER"
        assert "INVESTIGATING" in row.detail


def test_reply_logged_without_message_content() -> None:
    cid = _case_id()
    _web("TT001").post(f"/admin/cases/{cid}/reply", data={"message": "NOI-DUNG-BI-MAT-XYZ"}, follow_redirects=False)
    with SessionLocal() as db:
        rows = db.query(AuditLog).filter_by(action="case.reply", target=f"case:{cid}").all()
        assert rows
        assert all("NOI-DUNG-BI-MAT-XYZ" not in (r.detail + r.target) for r in db.query(AuditLog).all())


def test_admin_user_actions_logged() -> None:
    web = _web("AD001")
    web.post("/admin/users/create", data={"employee_code": "AUD_NEW", "full_name": "Thử", "department": "QA",
                                         "role": "EMPLOYEE", "password": "Password123@"}, follow_redirects=False)
    assert _count(action="user.create", target="user:AUD_NEW") == 1
    with SessionLocal() as db:
        uid = db.query(User).filter(User.employee_code == "AUD_NEW").one().id
    web.post(f"/admin/users/toggle/{uid}", follow_redirects=False)
    assert _count(action="user.lock", target="user:AUD_NEW") == 1


def test_employee_app_activity_not_logged() -> None:
    """Đăng nhập app / xin chữ ký mù / đọc tin của nhân viên KHÔNG được ghi (chống đối chiếu thời gian)."""
    with SessionLocal() as db:
        before = db.query(AuditLog).count()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login", data={"username": "NV002", "password": "employee123"}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    c.get("/api/v1/posts")
    c.post("/api/v1/compliance/blind-sign", json={"blinded_hash": "không-phải-số"})
    with SessionLocal() as db:
        assert db.query(AuditLog).count() == before


def test_audit_page_visible_to_board_only() -> None:
    assert _web("GD001").get("/admin/audit").status_code == 200
    for code in ("AD001", "TT001"):
        r = _web(code).get("/admin/audit", follow_redirects=False)
        assert r.status_code == 303
