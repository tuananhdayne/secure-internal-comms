import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import engine, SessionLocal, Base
from app.models.identified import User
from app.models.anonymous import WhistleCase
from app.core.security import get_password_hash, create_access_token
from app.crypto.key_manager import key_manager
from app.crypto.ecies import ecies_encrypt
from app.api.v1.officer import router as officer_router

app = FastAPI()
app.include_router(officer_router, prefix="/api/v1/officer")
client = TestClient(app)

officer_token = ""
employee_token = ""
test_case_id = 0
RAW_TITLE = "Sai phạm tài chính nghiêm trọng"
RAW_DESC = "Phát hiện lập khống hóa đơn 500 triệu đồng."


def setup_module(module):
    global officer_token, employee_token, test_case_id
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    officer = User(
        employee_code="TT_OFFICER_TEST",
        password_hash=get_password_hash("pass123"),
        full_name="Lê Thanh Tra Test",
        department="Thanh tra",
        role="COMPLIANCE_OFFICER"
    )
    emp = User(
        employee_code="NV_OFFICER_TEST",
        password_hash=get_password_hash("pass123"),
        full_name="Nhân viên Test",
        department="Kho",
        role="EMPLOYEE"
    )
    db.add(officer)
    db.add(emp)
    db.commit()
    db.refresh(officer)
    db.refresh(emp)

    officer_token = create_access_token(subject=str(officer.id), role=officer.role)
    employee_token = create_access_token(subject=str(emp.id), role=emp.role)

    # Mã hóa ECIES bằng khóa công khai của Thanh tra
    officer_pub_hex = key_manager.ec_public_key_hex
    payload = ecies_encrypt(officer_pub_hex, f"{RAW_TITLE}|||{RAW_DESC}".encode("utf-8"))

    case = WhistleCase(
        case_token="case-uuid-officer-test",
        category="THAM_NHUNG",
        encrypted_title=payload["ciphertext"][:32],
        encrypted_description=payload["ciphertext"],
        payload_ephemeral_pub=payload["ephemeral_public_key"],
        payload_iv=payload["iv"],
        payload_auth_tag=payload["auth_tag"],
        unblinded_signature="0x123456",
        case_public_key="04" + "b" * 128,
        status="PENDING",
        created_bucket=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    test_case_id = case.id
    db.close()


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_employee_forbidden_officer_routes():
    resp = client.get(
        "/api/v1/officer/cases",
        headers={"Authorization": f"Bearer {employee_token}"}
    )
    assert resp.status_code == 403


def test_officer_list_and_decrypt_case():
    # 1. Danh sách vụ việc
    list_resp = client.get(
        "/api/v1/officer/cases",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert list_resp.status_code == 200
    cases = list_resp.json()
    assert len(cases) >= 1
    assert cases[0]["case_token"] == "case-uuid-officer-test"

    # 2. Giải mã hồ sơ
    decrypt_resp = client.get(
        f"/api/v1/officer/cases/{test_case_id}/decrypt",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert decrypt_resp.status_code == 200
    data = decrypt_resp.json()
    assert RAW_TITLE in data["decrypted_title"]
    assert RAW_DESC in data["decrypted_description"]


def test_officer_update_status_and_reply():
    # Cập nhật trạng thái
    status_resp = client.patch(
        f"/api/v1/officer/cases/{test_case_id}/status",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"status": "INVESTIGATING"}
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "INVESTIGATING"

    # Trả lời điều tra
    reply_resp = client.post(
        f"/api/v1/officer/cases/{test_case_id}/reply",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={
            "ephemeral_pub_key": "04" + "f" * 128,
            "nonce_iv": "1" * 24,
            "encrypted_message": "enc_reply_hex",
            "auth_tag": "2" * 32,
            "digital_signature": "sig_hex"
        }
    )
    assert reply_resp.status_code == 201
    assert reply_resp.json()["sender_type"] == "COMPLIANCE_OFFICER"
