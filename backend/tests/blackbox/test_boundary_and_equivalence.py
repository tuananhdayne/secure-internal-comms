"""Black-Box Functional Tests: Equivalence Partitioning, Boundary Value Analysis & State Transitions.

Kiểm thử Hộp đen (Black-Box Testing) theo 4 kỹ thuật chuẩn:
1. Phân hoạch tương đương (Equivalence Partitioning - EP): Role hợp lệ vs không hợp lệ, chữ ký hex hợp lệ vs sai định dạng.
2. Phân tích giá trị biên (Boundary Value Analysis - BVA): Hạn ngạch ký mù (Quota = 1, 5 [Max], 6 [Max+1 -> 429]).
3. Kiểm thử chuyển đổi trạng thái (State Transition Testing): Vòng đời hồ sơ tố cáo (`RECEIVED` -> `UNDER_INVESTIGATION` -> `INVESTIGATING` -> `RESOLVED` -> `REJECTED` vs trạng thái không hợp lệ).
4. Kiểm thử đoán lỗi & vệ sinh đường dẫn (Error Guessing / Path Traversal): Tên file chứa `../../` khi upload minh chứng.
"""

from datetime import datetime, timezone
import hashlib
import io
import time
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, SessionLocal, Base
from app.models.identified import User, BlindSignQuota
from app.models.anonymous import WhistleCase
from app.core.security import create_access_token, get_password_hash
from app.crypto.blind_signature import (
    BlindSignatureEngine,
    simulate_client_blinding,
    simulate_client_unblinding,
)
from app.crypto.key_manager import key_manager

client = TestClient(app)


def setup_module(module) -> None:
    Base.metadata.create_all(bind=engine)


def test_bva_blind_sign_quota_boundaries() -> None:
    """BB-BVA-01: Phân tích giá trị biên (BVA) trên hạn ngạch ký mù tuần (Min=1, Max=5, Max+1=6)."""
    db = SessionLocal()
    emp = User(
        employee_code="EMP_BVA_QUOTA",
        full_name="BVA Quota Tester",
        password_hash=get_password_hash("Pass123@"),
        role="EMPLOYEE",
        department="QA",
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    token = create_access_token(subject=str(emp.id), role=emp.role)
    headers = {"Authorization": f"Bearer {token}"}
    e, n = key_manager.rsa_public_numbers

    try:
        # Biên dưới (1) tới Biên trên (5): Tất cả phải trả về HTTP 200
        for count in range(1, 6):
            m_star, _ = simulate_client_blinding(1000 + count, e, n)
            resp = client.post(
                "/api/v1/compliance/blind-sign",
                json={"blinded_hash": hex(m_star)[2:]},
                headers=headers,
            )
            assert resp.status_code == 200, f"Failed at boundary count={count}: {resp.text}"
            assert resp.json()["remaining_quota"] == 5 - count

        # Vượt biên trên (Max + 1 = 6): Bắt buộc bị chặn với HTTP 429 Too Many Requests
        m_star_over, _ = simulate_client_blinding(9999, e, n)
        resp_over = client.post(
            "/api/v1/compliance/blind-sign",
            json={"blinded_hash": hex(m_star_over)[2:]},
            headers=headers,
        )
        assert resp_over.status_code == 429
    finally:
        db.query(BlindSignQuota).filter(BlindSignQuota.user_id == emp.id).delete()
        db.delete(emp)
        db.commit()
        db.close()


def test_ep_admin_create_user_role_partitions() -> None:
    """BB-EP-01: Phân hoạch tương đương (EP) cho trường `role` khi tạo tài khoản."""
    db = SessionLocal()
    admin = User(
        employee_code="ADM_EP_01",
        full_name="System Admin EP",
        password_hash=get_password_hash("Admin123@"),
        role="SYSTEM_ADMIN",
        department="IT",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    admin_token = create_access_token(subject=str(admin.id), role=admin.role)
    client.cookies.set("admin_token", admin_token)

    try:
        # Phân hoạch không hợp lệ (Invalid Partition): Role ngoài tập cho phép -> HTTP 400
        resp_invalid = client.post(
            "/admin/users/create",
            data={
                "employee_code": "EMP_INVALID_ROLE",
                "full_name": "Invalid Role User",
                "department": "IT",
                "role": "SUPER_HACKER",
                "password": "Password123@",
            },
            follow_redirects=False,
        )
        assert resp_invalid.status_code == 400
    finally:
        client.cookies.clear()
        db.delete(admin)
        db.commit()
        db.close()


def test_state_transition_case_lifecycle() -> None:
    """BB-ST-01: Kiểm thử chuyển đổi trạng thái (State Transition) của hồ sơ tố cáo."""
    db = SessionLocal()
    officer = User(
        employee_code="OFF_ST_01",
        full_name="Officer State Tester",
        password_hash=get_password_hash("Officer123@"),
        role="COMPLIANCE_OFFICER",
        department="Compliance",
    )
    case = WhistleCase(
        case_token=f"CASE-ST-{int(time.time())}",
        category="Kiểm thử trạng thái",
        encrypted_title="aa",
        encrypted_description="bb",
        payload_ephemeral_pub="04" + "11" * 64,
        payload_iv="22" * 12,
        payload_auth_tag="33" * 16,
        case_public_key="04" + "44" * 64,
        unblinded_signature="55" * 32,
        status="RECEIVED",
        created_bucket=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0),
    )
    db.add_all([officer, case])
    db.commit()
    db.refresh(officer)
    db.refresh(case)

    officer_token = create_access_token(subject=str(officer.id), role=officer.role)
    headers = {"Authorization": f"Bearer {officer_token}"}

    try:
        # Chuyển đổi hợp lệ qua REST API: RECEIVED -> UNDER_INVESTIGATION -> INVESTIGATING -> RESOLVED -> REJECTED
        for next_status in ["UNDER_INVESTIGATION", "INVESTIGATING", "RESOLVED", "REJECTED"]:
            resp = client.patch(
                f"/api/v1/officer/cases/{case.id}/status",
                json={"status": next_status},
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == next_status

        # Chuyển đổi không hợp lệ: Trạng thái nằm ngoài tập trạng thái cho phép -> HTTP 400
        resp_bad = client.patch(
            f"/api/v1/officer/cases/{case.id}/status",
            json={"status": "ARCHIVED_UNKNOWN"},
            headers=headers,
        )
        assert resp_bad.status_code == 400
    finally:
        db.delete(case)
        db.delete(officer)
        db.commit()
        db.close()


def test_error_guessing_path_traversal_filename_sanitized() -> None:
    """BB-EG-01: Kiểm thử đoán lỗi (Error Guessing) với tên file đính kèm chứa Path Traversal `../../`."""
    e, n = key_manager.rsa_public_numbers
    case_priv = ec.generate_private_key(ec.SECP256R1())
    case_pub_hex = case_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    ).hex()

    case_token = f"CASE-PATH-{int(time.time())}"
    file_bytes = b"SAFE_BINARY_EVIDENCE_CONTENT"
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    h = BlindSignatureEngine.compute_payload_hash(
        category="An toàn thông tin",
        encrypted_title="enc_title",
        encrypted_description="enc_desc",
        case_token=case_token,
        case_public_key=case_pub_hex,
        evidence_file_hashes=[file_hash],
    )
    m_star, r = simulate_client_blinding(h, e, n)
    s_star = BlindSignatureEngine.blind_sign(m_star)
    s_hex = hex(simulate_client_unblinding(s_star, r, n))[2:]

    resp = client.post(
        "/api/v1/anonymous/cases",
        data={
            "category": "An toàn thông tin",
            "encrypted_title": "enc_title",
            "encrypted_description": "enc_desc",
            "payload_ephemeral_pub": "04" + "11" * 64,
            "payload_iv": "22" * 12,
            "payload_auth_tag": "33" * 16,
            "case_token": case_token,
            "case_public_key": case_pub_hex,
            "unblinded_signature": s_hex,
        },
        files=[("files", ("../../../etc/traversal_test.bin", io.BytesIO(file_bytes), "application/octet-stream"))],
    )
    assert resp.status_code == 201

    # Kiểm tra qua cổng tra cứu ẩn danh: file_url không chứa `..` và không lộ đường dẫn tuyệt đối của máy chủ
    detail_resp = client.get(f"/api/v1/anonymous/cases/{case_token}")
    assert detail_resp.status_code == 200
    evidences = detail_resp.json()["evidences"]
    assert len(evidences) == 1
    assert evidences[0]["file_url"].startswith("/uploads/evidences/")
    assert ".." not in evidences[0]["file_url"]
    assert evidences[0]["file_url"].endswith("_traversal_test.bin")
