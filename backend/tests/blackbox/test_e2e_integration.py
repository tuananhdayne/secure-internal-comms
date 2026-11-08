"""End-to-End Integration Test Suite.
Kiểm tra luồng liên thông toàn diện giữa Mobile Client, Backend Server và Ban Thanh Tra:
1. Đăng nhập Nhân viên (NV001) -> Nhận JWT Bearer Token.
2. Lấy Public Keys của Ban Thanh Tra (RSA e, N + ECC chat pub).
3. Client sinh khóa Case ECC P-256, mã hóa ECIES Title & Description.
4. Client tính mã băm H và làm mù m* = (H * r^e) mod N.
5. Client gửi m* lên endpoint Compliance xin chữ ký mù -> Nhận s*.
6. Client bóc mù s = (s* * r^-1) mod N.
7. Client nộp ẩn danh (Zero-Knowledge) qua Anonymous Endpoint kèm file bằng chứng.
8. Ban Thanh tra (TT001) đăng nhập, xem danh sách vụ việc.
9. Ban Thanh tra dùng Private Key ECC giải mã thành công Title và Description gốc!
10. Ban Thanh tra cập nhật trạng thái (UNDER_INVESTIGATION) và gửi tin nhắn phản hồi mã hóa.
11. Client nặc danh tra cứu hồ sơ và giải mã tin nhắn phản hồi từ Thanh tra.
"""

import hashlib
import io
import time
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine, Base, SessionLocal
from app.db.seed import seed_database
from app.crypto.blind_signature import (
    BlindSignatureEngine,
    simulate_client_blinding,
    simulate_client_unblinding,
)
from app.crypto.ecies import ecies_encrypt, ecies_decrypt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database(db)
    db.close()
    with TestClient(app) as test_client:
        yield test_client


def test_complete_end_to_end_flow(client: TestClient):
    # =========================================================================
    # BƯỚC 1: NHÂN VIÊN ĐĂNG NHẬP LẤY JWT TOKEN (CỤM 1)
    # =========================================================================
    emp_login = client.post(
        "/api/v1/auth/login",
        data={"username": "NV001", "password": "employee123"}
    )
    assert emp_login.status_code == 200
    emp_token = emp_login.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # =========================================================================
    # BƯỚC 2: LẤY PUBLIC KEYS CỦA BAN THANH TRA (RSA + ECC)
    # =========================================================================
    pk_resp = client.get("/api/v1/compliance/public-keys", headers=emp_headers)
    assert pk_resp.status_code == 200
    pk_data = pk_resp.json()
    rsa_e = int(pk_data["blind_sign_pub"]["e"], 16)
    rsa_n = int(pk_data["blind_sign_pub"]["n"], 16)
    officer_chat_pub = pk_data["chat_pub_hex"]

    # =========================================================================
    # BƯỚC 3: MÃ HÓA NỘI DUNG TỐ GIÁC BẰNG ECIES VÀ CHUẨN BỊ BẰNG CHỨNG
    # =========================================================================
    case_priv = ec.generate_private_key(ec.SECP256R1())
    case_pub_hex = case_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    ).hex()
    case_token = f"CASE-{int(time.time())}-E2E"
    category = "Tham ô tài sản"
    raw_title = "Gian lận quỹ tài chính chi nhánh miền Bắc"
    raw_desc = "Phát hiện lập 2 sổ sách kế toán để trốn thuế và chia chác tiền chênh lệch."

    # Mã hóa ECIES Title và Description kết hợp
    full_content = f"{raw_title}|||{raw_desc}".encode("utf-8")
    enc_payload = ecies_encrypt(officer_chat_pub, full_content)

    # File bằng chứng sạch
    evidence_bytes = b"EXCEL_FINANCIAL_FRAUD_DATA_2026_AUDIT"
    evidence_hash = hashlib.sha256(evidence_bytes).hexdigest()

    # =========================================================================
    # BƯỚC 4: TÍNH TOÁN MÃ BĂM TOÁN HỌC H VÀ LÀM MÙ m*
    # =========================================================================
    target_h = BlindSignatureEngine.compute_payload_hash(
        category=category,
        encrypted_title="ECIES_PROTECTED",
        encrypted_description=enc_payload["ciphertext"],
        case_token=case_token,
        case_public_key=case_pub_hex,
        evidence_file_hashes=[evidence_hash]
    )

    m_star, r = simulate_client_blinding(target_h, rsa_e, rsa_n)
    m_star_hex = hex(m_star)[2:]

    # =========================================================================
    # BƯỚC 5: NHÂN VIÊN GỬI m* XIN CHỮ KÝ MÙ BAN THANH TRA
    # =========================================================================
    blind_sign_resp = client.post(
        "/api/v1/compliance/blind-sign",
        json={"blinded_hash": m_star_hex},
        headers=emp_headers
    )
    assert blind_sign_resp.status_code == 200
    s_star = int(blind_sign_resp.json()["blind_signature"], 16)

    # =========================================================================
    # BƯỚC 6: BÓC MÙ THU HỒI CHỮ KÝ GỐC s
    # =========================================================================
    s = simulate_client_unblinding(s_star, r, rsa_n)
    s_hex = hex(s)[2:]

    # Kiểm tra tính hợp lệ toán học cục bộ: s^e mod N == H
    assert pow(s, rsa_e, rsa_n) == target_h

    # =========================================================================
    # BƯỚC 7: NỘP HỒ SƠ ẨN DANH (ZERO-KNOWLEDGE - CỤM 2)
    # =========================================================================
    submit_resp = client.post(
        "/api/v1/anonymous/cases",
        data={
            "category": category,
            "encrypted_title": "ECIES_PROTECTED",
            "encrypted_description": enc_payload["ciphertext"],
            "payload_ephemeral_pub": enc_payload["ephemeral_public_key"],
            "payload_iv": enc_payload["iv"],
            "payload_auth_tag": enc_payload["auth_tag"],
            "case_token": case_token,
            "case_public_key": case_pub_hex,
            "unblinded_signature": s_hex
        },
        files=[("files", ("audit.xlsx", io.BytesIO(evidence_bytes), "application/octet-stream"))]
    )
    assert submit_resp.status_code == 201
    assert submit_resp.json()["case_token"] == case_token
    assert submit_resp.json()["status"] == "PENDING"

    # =========================================================================
    # BƯỚC 8: BAN THANH TRA (TT001) TIẾP NHẬN & GIẢI MÃ ĐIỀU TRA
    # =========================================================================
    officer_login = client.post(
        "/api/v1/auth/login",
        data={"username": "TT001", "password": "officer123"}
    )
    assert officer_login.status_code == 200
    officer_token = officer_login.json()["access_token"]
    officer_headers = {"Authorization": f"Bearer {officer_token}"}

    # Xem danh sách hồ sơ
    cases_resp = client.get("/api/v1/officer/cases", headers=officer_headers)
    assert cases_resp.status_code == 200
    all_cases = cases_resp.json()
    target_case = next(c for c in all_cases if c["case_token"] == case_token)
    case_id = target_case["id"]

    # Giải mã hồ sơ bằng Officer Private Key
    decrypt_resp = client.get(f"/api/v1/officer/cases/{case_id}/decrypt", headers=officer_headers)
    assert decrypt_resp.status_code == 200
    decrypted_data = decrypt_resp.json()
    assert decrypted_data["decrypted_title"] == raw_title

    # Cập nhật trạng thái sang ĐANG XÁC MINH
    status_update = client.patch(
        f"/api/v1/officer/cases/{case_id}/status",
        json={"status": "UNDER_INVESTIGATION"},
        headers=officer_headers
    )
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "UNDER_INVESTIGATION"

    # Ban Thanh tra gửi phản hồi mã hóa E2EE tới Người tố cáo
    reply_raw = "Ban Thanh tra đã tiếp nhận và đang tiến hành kiểm tra đột xuất tại chi nhánh."
    reply_payload = ecies_encrypt(case_pub_hex, reply_raw.encode("utf-8"))

    officer_reply = client.post(
        f"/api/v1/officer/cases/{case_id}/reply",
        json={
            "ephemeral_pub_key": reply_payload["ephemeral_public_key"],
            "nonce_iv": reply_payload["iv"],
            "encrypted_message": reply_payload["ciphertext"],
            "auth_tag": reply_payload["auth_tag"],
            "digital_signature": "OFFICER_SIGNATURE_HEX"
        },
        headers=officer_headers
    )
    assert officer_reply.status_code == 201

    # =========================================================================
    # BƯỚC 9: NGƯỜI TỐ CÁO TRA CỨU HỒ SƠ ẨN DANH & GIẢI MÃ PHẢN HỒI
    # =========================================================================
    status_query = client.get(f"/api/v1/anonymous/cases/{case_token}")
    assert status_query.status_code == 200
    case_detail = status_query.json()
    assert case_detail["status"] == "UNDER_INVESTIGATION"
    assert len(case_detail["messages"]) == 1

    officer_msg = case_detail["messages"][0]
    assert officer_msg["sender_type"] == "COMPLIANCE_OFFICER"

    # Người tố cáo dùng case_priv giải mã phản hồi của Ban Thanh tra
    decrypted_reply_bytes = ecies_decrypt(
        recipient_priv_key=case_priv,
        ephemeral_pub_hex=officer_msg["ephemeral_pub_key"],
        iv_hex=officer_msg["nonce_iv"],
        ciphertext_hex=officer_msg["encrypted_message"],
        tag_hex=officer_msg["auth_tag"]
    )
    assert "Ban Thanh tra đã tiếp nhận" in decrypted_reply_bytes.decode("utf-8")
