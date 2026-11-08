import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import engine, SessionLocal, Base
from app.models.identified import User
from app.core.security import get_password_hash, create_access_token
from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import BlindSignatureEngine, simulate_client_blinding, simulate_client_unblinding
from app.api.v1.compliance import router as compliance_router

app = FastAPI()
app.include_router(compliance_router, prefix="/api/v1/compliance")
client = TestClient(app)

employee_token = ""
user_id = 0


def setup_module(module):
    global employee_token, user_id
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    emp = User(
        employee_code="NV_COMPLIANCE_TEST",
        password_hash=get_password_hash("pass123"),
        full_name="Nhân viên Compliance Test",
        department="Kế toán",
        role="EMPLOYEE"
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    user_id = emp.id
    employee_token = create_access_token(subject=str(emp.id), role=emp.role)
    db.close()


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_get_compliance_public_keys():
    response = client.get("/api/v1/compliance/public-keys")
    assert response.status_code == 200
    data = response.json()
    assert "blind_sign_pub" in data
    assert "e" in data["blind_sign_pub"]
    assert "n" in data["blind_sign_pub"]
    assert "chat_pub_hex" in data
    assert len(data["chat_pub_hex"]) == 130


def test_blind_sign_flow_and_quota_enforcement():
    # 1. Lấy public key RSA
    e, n = key_manager.rsa_public_numbers

    # Giả lập hồ sơ tố cáo & tính H
    H = BlindSignatureEngine.compute_payload_hash(
        category="THAM_NHUNG",
        encrypted_title="enc_title",
        encrypted_description="enc_desc",
        case_token="case-uuid-9999",
        case_public_key="04" + "a" * 128,
        evidence_file_hashes=["hash1", "hash2"]
    )

    # 2. Client làm mù: m* = (H * r^e) mod N
    m_star, r = simulate_client_blinding(H, e, n)

    # 3. Gửi xin ký mù lần 1
    resp1 = client.post(
        "/api/v1/compliance/blind-sign",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"blinded_hash": hex(m_star)}
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["remaining_quota"] == 4
    s_star = int(data1["blind_signature"], 16)

    # 4. Client bóc mù: s = (s* * r^-1) mod N
    s = simulate_client_unblinding(s_star, r, n)

    # 5. Xác minh chữ ký mù toàn vẹn: s^e mod N == H
    assert BlindSignatureEngine.verify(H, s) is True

    # 6. Gửi tiếp 4 lần nữa (tổng cộng 5 lần = hết quota tuần)
    for i in range(4):
        resp = client.post(
            "/api/v1/compliance/blind-sign",
            headers={"Authorization": f"Bearer {employee_token}"},
            json={"blinded_hash": hex(m_star)}
        )
        assert resp.status_code == 200

    # 7. Lần thứ 6 -> Bị chặn 429 Too Many Requests
    resp_over = client.post(
        "/api/v1/compliance/blind-sign",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"blinded_hash": hex(m_star)}
    )
    assert resp_over.status_code == 429
    assert "hạn mức" in resp_over.json()["detail"].lower()
