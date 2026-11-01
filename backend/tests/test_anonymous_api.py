import io
import hashlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization

from app.db.session import engine, SessionLocal, Base
from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import BlindSignatureEngine, simulate_client_blinding, simulate_client_unblinding
from app.api.v1.anonymous import router as anonymous_router

app = FastAPI()
app.include_router(anonymous_router, prefix="/api/v1/anonymous")
client = TestClient(app)


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_submit_valid_case_success():
    # 1. Client sinh case_token và cặp khóa EC tạm thời
    case_token = "case-uuid-valid-1234"
    case_priv_key = ec.generate_private_key(ec.SECP256R1())
    case_pub_bytes = case_priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    case_pub_hex = case_pub_bytes.hex()

    # 2. Chuẩn bị file bằng chứng giả lập (đã mã hóa)
    file_bytes = b"Encrypted file content via File_Key (AES-256-GCM)"
    file_sha256 = hashlib.sha256(file_bytes).hexdigest()

    category = "TAI_CHINH"
    enc_title = "0123456789abcdef"
    enc_desc = "fedcba9876543210"

    # 3. Tính mã băm toàn vẹn H
    H = BlindSignatureEngine.compute_payload_hash(
        category=category,
        encrypted_title=enc_title,
        encrypted_description=enc_desc,
        case_token=case_token,
        case_public_key=case_pub_hex,
        evidence_file_hashes=[file_sha256]
    )

    # 4. Làm mù & xin chữ ký mù
    e, n = key_manager.rsa_public_numbers
    m_star, r = simulate_client_blinding(H, e, n)
    s_star = BlindSignatureEngine.blind_sign(m_star)
    s = simulate_client_unblinding(s_star, r, n)
    unblinded_sig_hex = hex(s)

    # 5. Nộp hồ sơ qua API Zero-Knowledge
    files = [
        ("files", ("evidence1.bin", io.BytesIO(file_bytes), "application/octet-stream"))
    ]
    data = {
        "category": category,
        "encrypted_title": enc_title,
        "encrypted_description": enc_desc,
        "payload_ephemeral_pub": "04" + "a" * 128,
        "payload_iv": "b" * 24,
        "payload_auth_tag": "c" * 32,
        "case_token": case_token,
        "case_public_key": case_pub_hex,
        "unblinded_signature": unblinded_sig_hex
    }

    response = client.post("/api/v1/anonymous/cases", data=data, files=files)
    assert response.status_code == 201
    res_json = response.json()
    assert res_json["case_token"] == case_token
    assert res_json["status"] == "PENDING"


def test_submit_case_tampered_signature_fails():
    files = [
        ("files", ("fake.bin", io.BytesIO(b"data"), "application/octet-stream"))
    ]
    data = {
        "category": "TAI_CHINH",
        "encrypted_title": "title",
        "encrypted_description": "desc",
        "payload_ephemeral_pub": "04" + "a" * 128,
        "payload_iv": "b" * 24,
        "payload_auth_tag": "c" * 32,
        "case_token": "case-uuid-fake-sig",
        "case_public_key": "04" + "b" * 128,
        "unblinded_signature": "0x1234567890abcdef"  # Chữ ký giả mạo
    }
    response = client.post("/api/v1/anonymous/cases", data=data, files=files)
    assert response.status_code == 400
    assert "chữ ký" in response.json()["detail"].lower()


def test_get_case_status_and_chat():
    case_token = "case-uuid-valid-1234"
    status_resp = client.get(f"/api/v1/anonymous/cases/{case_token}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["case_token"] == case_token
    assert len(data["evidences"]) == 1
