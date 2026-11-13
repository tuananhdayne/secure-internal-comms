import io
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from app.main import app
from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import BlindSignatureEngine
from app.crypto.ecies import ecies_encrypt
from app.db.session import engine, SessionLocal, Base
from app.models.anonymous import WhistleCase, CaseEvidence
from app.models.identified import User


def setup_module(module):
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_submit_case_with_multimedia_evidences(client):
    """Kiểm tra quy trình nộp hồ sơ đính kèm nhiều định dạng tệp (ảnh, âm thanh, video, tài liệu)."""
    # 1. Chuẩn bị nội dung mã hóa ECIES
    officer_pub_hex = key_manager.ec_public_key_hex
    plaintext = "Tiêu đề tham nhũng đa phương tiện|||Nội dung mô tả chi tiết kèm video, ghi âm hiện trường.".encode("utf-8")
    enc_payload = ecies_encrypt(officer_pub_hex, plaintext)

    case_token = "CASE-MULTIMEDIA-TEST-999"
    category = "Tham nhũng tài chính"
    case_pub_key = "04" + "aa" * 64

    # 2. Tạo 4 tệp bằng chứng giả lập: ảnh PNG, ghi âm MP3, video MP4, tài liệu PDF
    img_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    audio_content = b"ID3\x03\x00\x00\x00\x00\x00#MOCK_VOICE_RECORDING_DATA"
    video_content = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42MOCK_VIDEO_STREAM"
    doc_content = b"%PDF-1.4 mock confidential report attachment"

    import hashlib
    img_hash = hashlib.sha256(img_content).hexdigest()
    audio_hash = hashlib.sha256(audio_content).hexdigest()
    video_hash = hashlib.sha256(video_content).hexdigest()
    doc_hash = hashlib.sha256(doc_content).hexdigest()

    file_hashes = [img_hash, audio_hash, video_hash, doc_hash]

    # 3. Tính mã băm H và xin chữ ký mù
    H = BlindSignatureEngine.compute_payload_hash(
        category=category,
        encrypted_title=enc_payload["ciphertext"][:32],
        encrypted_description=enc_payload["ciphertext"],
        case_token=case_token,
        case_public_key=case_pub_key,
        evidence_file_hashes=file_hashes
    )

    # Giả lập làm mù và ký mù
    r = 13579
    e, n = key_manager.rsa_public_numbers
    d, _ = key_manager.rsa_private_numbers
    m_star = (H * pow(r, e, n)) % n
    s_star = pow(m_star, d, n)
    # Bóc mù
    s = (s_star * pow(r, -1, n)) % n
    s_hex = hex(s)

    # 4. Gửi request multipart
    files = [
        ("files", ("evidence_scene.png", io.BytesIO(img_content), "image/png")),
        ("files", ("confidential_audio.mp3", io.BytesIO(audio_content), "audio/mpeg")),
        ("files", ("security_cam.mp4", io.BytesIO(video_content), "video/mp4")),
        ("files", ("audit_report.pdf", io.BytesIO(doc_content), "application/pdf"))
    ]

    data = {
        "category": category,
        "encrypted_title": enc_payload["ciphertext"][:32],
        "encrypted_description": enc_payload["ciphertext"],
        "payload_ephemeral_pub": enc_payload["ephemeral_public_key"],
        "payload_iv": enc_payload["iv"],
        "payload_auth_tag": enc_payload["auth_tag"],
        "case_token": case_token,
        "case_public_key": case_pub_key,
        "unblinded_signature": s_hex
    }

    res = client.post("/api/v1/anonymous/cases", data=data, files=files)
    assert res.status_code == 201, f"Lỗi nộp hồ sơ: {res.text}"
    resp_json = res.json()
    assert resp_json["case_token"] == case_token
    assert resp_json["status"] == "PENDING"

    # 5. Tra cứu trạng thái hồ sơ qua anonymous endpoint
    status_res = client.get(f"/api/v1/anonymous/cases/{case_token}")
    assert status_res.status_code == 200
    status_json = status_res.json()
    assert len(status_json["evidences"]) == 4

    returned_mimes = [e["mime_type"] for e in status_json["evidences"]]
    assert "image/png" in returned_mimes
    assert "audio/mpeg" in returned_mimes
    assert "video/mp4" in returned_mimes
    assert "application/pdf" in returned_mimes

    for ev in status_json["evidences"]:
        assert ev["file_url"].startswith("/uploads/evidences/")
        assert len(ev["file_sha256_hash"]) == 64
