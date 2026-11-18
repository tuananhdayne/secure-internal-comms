"""Kiểm thử hồi quy cho các lỗ hổng phát hiện trong đợt review (11/2026).

1. Stored XSS: tên tệp / MIME type do client gửi lên được render vào trang Thanh tra.
2. Tệp bằng chứng phục vụ công khai không có header chống sniff / sandbox.
3. RBAC Web: Cán bộ Thanh tra không được đăng / xóa bài truyền thông.
4. Cookie JWT có `sub` không phải số không được làm sập server (HTTP 500).
"""
import hashlib
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import BlindSignatureEngine
from app.crypto.ecies import ecies_encrypt
from app.core.security import create_access_token, get_password_hash
from app.db.session import engine, Base, SessionLocal
from app.models.anonymous import WhistleCase, CaseEvidence, CaseMessage
from app.models.identified import Post, User


def setup_module(module):
    Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _submit_case(client: TestClient, filename: str, mime: str, content: bytes = b"evidence-bytes",
                 pub: str = "04" + "aa" * 64, extra_files: int = 0):
    enc = ecies_encrypt(key_manager.ec_public_key_hex, "T|||D".encode())
    token = f"CASE-REG-{time.time_ns()}"
    h = BlindSignatureEngine.compute_payload_hash(
        category="PoC", encrypted_title=enc["ciphertext"][:32], encrypted_description=enc["ciphertext"],
        case_token=token, case_public_key=pub, evidence_file_hashes=[hashlib.sha256(content).hexdigest()],
    )
    d, n = key_manager.rsa_private_numbers
    sig = hex(pow(h, d, n))
    body = (
        f'--B\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + content + b"\r\n"
    for i in range(extra_files):
        body += (f'--B\r\nContent-Disposition: form-data; name="files"; filename="extra{i}.bin"\r\n'
                 f"Content-Type: application/octet-stream\r\n\r\n").encode() + content + b"\r\n"
    fields = {
        "category": "PoC", "encrypted_title": enc["ciphertext"][:32], "encrypted_description": enc["ciphertext"],
        "payload_ephemeral_pub": enc["ephemeral_public_key"], "payload_iv": enc["iv"],
        "payload_auth_tag": enc["auth_tag"], "case_token": token, "case_public_key": pub,
        "unblinded_signature": sig,
    }
    for k, v in fields.items():
        body += f'--B\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += b"--B--\r\n"
    resp = client.post(
        "/api/v1/anonymous/cases", content=body,
        headers={"Content-Type": "multipart/form-data; boundary=B"},
    )
    return resp, token


def _evidence_for(token: str) -> CaseEvidence:
    db = SessionLocal()
    try:
        case = db.query(WhistleCase).filter(WhistleCase.case_token == token).first()
        return case.evidences[0]
    finally:
        db.close()


def test_malicious_filename_and_mime_are_neutralized(client: TestClient):
    resp, token = _submit_case(
        client,
        filename="<img src=x onerror=alert(1)>.png",
        mime='text/plain"><img src=x onerror="alert(1)">',
    )
    assert resp.status_code == 201, resp.text
    ev = _evidence_for(token)
    from app.services.evidence import read_name
    stored_name = read_name(ev.file_url)
    for ch in '<>"\' ()=':
        assert ch not in stored_name
    assert stored_name.endswith(".png")
    assert ev.mime_type == "application/octet-stream"


def test_valid_mime_type_is_preserved(client: TestClient):
    resp, token = _submit_case(client, filename="ghi_am_hien_truong.mp3", mime="audio/mpeg")
    assert resp.status_code == 201, resp.text
    ev = _evidence_for(token)
    assert ev.mime_type == "audio/mpeg"
    from app.services.evidence import read_name
    assert read_name(ev.file_url) == "ghi_am_hien_truong.mp3"


def test_uploaded_html_is_served_sandboxed(client: TestClient):
    resp, token = _submit_case(client, filename="trap.html", mime="text/html",
                               content=b"<script>alert(document.cookie)</script>")
    assert resp.status_code == 201, resp.text
    ev = _evidence_for(token)
    # Không còn đường tải tĩnh công khai
    assert client.get("/uploads/evidences/" + ev.file_url.split(":", 1)[1]).status_code == 404
    # Chưa đăng nhập -> không tải được
    client.cookies.clear()
    assert client.get(f"/admin/evidence/{ev.id}").status_code == 401
    # Thanh tra tải được; HTML luôn là tệp tải về, kèm sandbox + nosniff
    _login_web(client, "TT_EVID", "OfficerPass123!")
    served = client.get(f"/admin/evidence/{ev.id}")
    assert served.status_code == 200
    assert served.content == b"<script>alert(document.cookie)</script>"
    assert served.headers.get("x-content-type-options") == "nosniff"
    assert "sandbox" in served.headers.get("content-security-policy", "")
    assert served.headers["content-disposition"].startswith("attachment")
    assert "text/html" not in served.headers["content-type"]
    client.cookies.clear()


def test_evidence_download_requires_case_permission(client: TestClient):
    """Quản trị / Ban Giám đốc không tải được bằng chứng (tách bạch nhiệm vụ)."""
    resp, token = _submit_case(client, filename="anh.png", mime="image/png", content=b"\x89PNG fake")
    assert resp.status_code == 201, resp.text
    ev = _evidence_for(token)
    for role in ("SYSTEM_ADMIN", "BOARD_DIRECTOR"):
        db = SessionLocal()
        try:
            u = User(employee_code=f"EV_{role}", full_name=role, department="QA", role=role,
                     password_hash=get_password_hash("x"), is_active=True)
            db.add(u); db.commit(); db.refresh(u)
            tok = create_access_token(subject=str(u.id), role=role)
        finally:
            db.close()
        client.cookies.clear()
        client.cookies.set("admin_token", tok)
        assert client.get(f"/admin/evidence/{ev.id}").status_code == 403
        client.headers["Authorization"] = f"Bearer {tok}"
        assert client.get(f"/api/v1/officer/evidence/{ev.id}").status_code == 403
        del client.headers["Authorization"]
    client.cookies.clear()


def _login_web(client: TestClient, code: str, pw: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.employee_code == code).first()
        if user is None:
            user = User(employee_code=code, full_name=code, department="QA", role="COMPLIANCE_OFFICER",
                        password_hash="", is_active=True)
            db.add(user)
        user.password_hash = get_password_hash(pw)
        user.is_active = True
        db.commit()
    finally:
        db.close()
    client.cookies.clear()
    r = client.post("/admin/login", data={"employee_code": code, "password": pw}, follow_redirects=False)
    assert r.status_code == 303


def test_officer_cannot_create_or_delete_posts_via_web(client: TestClient):
    _login_web(client, "TT001", "officer123")
    title = f"Officer post {time.time_ns()}"
    r = client.post("/admin/posts/create", data={"title": title, "content": "x"}, follow_redirects=False)
    assert r.status_code == 403
    db = SessionLocal()
    try:
        assert db.query(Post).filter(Post.title == title).first() is None
        target = db.query(Post).first()
        target_id = target.id if target else 1
    finally:
        db.close()
    r = client.post(f"/admin/posts/delete/{target_id}", follow_redirects=False)
    assert r.status_code == 403
    client.cookies.clear()


def test_non_numeric_sub_in_cookie_does_not_crash(client: TestClient):
    client.cookies.clear()
    bad = create_access_token(subject="not-a-number", role="SYSTEM_ADMIN")
    client.cookies.set("admin_token", bad)
    r = client.get("/admin/dashboard", follow_redirects=False)
    assert r.status_code == 303
    client.cookies.clear()


def test_admin_pages_send_anti_clickjacking_headers(client: TestClient):
    r = client.get("/admin/login")
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"


# ---------------------------------------------------------------------------
# Log an toàn & request_id (app/core/logging.py, app/core/middleware.py)
# ---------------------------------------------------------------------------

def test_every_response_has_request_id(client: TestClient):
    r = client.get("/health")
    assert len(r.headers.get("x-request-id", "")) == 12


def test_anonymous_requests_are_not_access_logged(client: TestClient, caplog):
    import logging
    caplog.set_level(logging.INFO)
    secret_token = "CASE-SECRET-TOKEN-DO-NOT-LOG"
    client.get(f"/api/v1/anonymous/cases/{secret_token}")
    client.get("/health")
    # Chỉ xét log của server (app.*); log "httpx" là của test client.
    text = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("app"))
    assert secret_token not in text
    assert "GET /health -> 200" in text           # route định danh vẫn được log
    assert "testclient" not in text                # không ghi địa chỉ client


def test_uvicorn_access_log_is_disabled():
    import logging
    assert logging.getLogger("uvicorn.access").disabled


def test_unhandled_error_returns_request_id_and_masks_token(client: TestClient, caplog, monkeypatch):
    import logging
    from app.api.v1 import anonymous as anon_module

    def boom(*args, **kwargs):
        raise RuntimeError("lỗi giả lập")

    monkeypatch.setattr(anon_module, "masked_signature_for_anonymous", boom)
    resp, token = _submit_case(client, filename="a.txt", mime="text/plain")
    assert resp.status_code == 201
    db = SessionLocal()
    try:
        case = db.query(WhistleCase).filter(WhistleCase.case_token == token).first()
        db.add(CaseMessage(case_id=case.id, sender_type="COMPLIANCE_OFFICER", ephemeral_pub_key="00",
                           nonce_iv="00", encrypted_message="00", auth_tag="00", digital_signature="x"))
        db.commit()
    finally:
        db.close()

    caplog.set_level(logging.INFO)
    r = client.get(f"/api/v1/anonymous/cases/{token}")
    assert r.status_code == 500
    body = r.json()
    assert body["request_id"] == r.headers["x-request-id"]
    server_logs = [r for r in caplog.records if r.name.startswith("app")]
    errors = [r for r in server_logs if r.name == "app.error"]
    assert errors and errors[0].request_id == body["request_id"]   # tra được traceback bằng request_id
    assert errors[0].exc_info is not None                           # có traceback đầy đủ
    text = "\n".join(r.getMessage() for r in server_logs)
    assert token not in text                                        # case_token đã bị che
    assert "{case_token}" in text


# ---------------------------------------------------------------------------
# Giới hạn tệp, chống phát lại tin nhắn, CORS, cảnh báo khóa JWT mặc định
# ---------------------------------------------------------------------------

def test_oversized_evidence_is_rejected_with_413(client: TestClient, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_EVIDENCE_FILE_MB", 1)
    resp, _ = _submit_case(client, filename="big.bin", mime="application/octet-stream",
                           content=b"x" * (1024 * 1024 + 1))
    assert resp.status_code == 413


def test_too_many_evidence_files_is_rejected_with_413(client: TestClient, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MAX_EVIDENCE_FILES", 2)
    resp, _ = _submit_case(client, filename="a.bin", mime="application/octet-stream", extra_files=2)
    assert resp.status_code == 413


def test_replayed_whistleblower_message_is_rejected(client: TestClient):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    case_key = ec.generate_private_key(ec.SECP256R1())
    pub = case_key.public_key().public_bytes(serialization.Encoding.X962,
                                             serialization.PublicFormat.UncompressedPoint).hex()
    resp, token = _submit_case(client, filename="a.txt", mime="text/plain", pub=pub)
    assert resp.status_code == 201, resp.text

    m = ecies_encrypt(key_manager.ec_public_key_hex, "Xin bổ sung chứng cứ".encode())
    payload = {
        "ephemeral_pub_key": m["ephemeral_public_key"], "nonce_iv": m["iv"],
        "encrypted_message": m["ciphertext"], "auth_tag": m["auth_tag"],
        "digital_signature": case_key.sign(m["ciphertext"].encode(), ec.ECDSA(hashes.SHA256())).hex(),
    }
    first = client.post(f"/api/v1/anonymous/cases/{token}/messages", json=payload)
    assert first.status_code == 201
    replay = client.post(f"/api/v1/anonymous/cases/{token}/messages", json=payload)
    assert replay.status_code == 409


def test_cors_does_not_allow_credentials(client: TestClient):
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_default_jwt_secret_is_replaced(tmp_path, monkeypatch):
    """Khóa công khai / quá ngắn bị thay bằng khóa ngẫu nhiên của máy chủ; khóa mạnh trong .env được giữ nguyên."""
    from app.core.config import Settings
    monkeypatch.setenv("KEYS_DIR", str(tmp_path))
    for weak in ("secure_internal_comms_secret_key_2026_defense", "short"):
        s = Settings(_env_file=None, JWT_SECRET_KEY=weak)
        assert s.jwt_secret_autogenerated and not s.uses_insecure_jwt_secret and s.JWT_SECRET_KEY != weak
    strong = Settings(_env_file=None, JWT_SECRET_KEY="k" * 48)
    assert not strong.jwt_secret_autogenerated and strong.JWT_SECRET_KEY == "k" * 48


def test_public_jwt_secrets_cannot_forge_tokens(client: TestClient):
    """Khóa JWT công khai trong mã nguồn / .env.example KHÔNG BAO GIỜ được dùng để ký (tự thay bằng khóa ngẫu nhiên)."""
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.core.config import INSECURE_JWT_SECRETS, settings
    assert settings.JWT_SECRET_KEY not in INSECURE_JWT_SECRETS and len(settings.JWT_SECRET_KEY) >= 32
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "SYSTEM_ADMIN").first()
        if admin is None:
            admin = User(employee_code="JWT_ADM", full_name="a", department="IT", role="SYSTEM_ADMIN",
                         password_hash=get_password_hash("x"), is_active=True)
            db.add(admin); db.commit(); db.refresh(admin)
        uid = admin.id
    finally:
        db.close()
    for secret in INSECURE_JWT_SECRETS:
        forged = jwt.encode({"sub": str(uid), "role": "SYSTEM_ADMIN",
                             "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, secret, algorithm="HS256")
        client.cookies.clear()
        client.cookies.set("admin_token", forged)
        assert client.get("/admin/users", follow_redirects=False).status_code == 303
        assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    client.cookies.clear()


def test_insecure_env_secret_is_replaced(tmp_path, monkeypatch):
    from app.core.config import Settings
    monkeypatch.setenv("JWT_SECRET_KEY", "change_this_to_a_secure_random_secret_in_production")
    monkeypatch.setenv("KEYS_DIR", str(tmp_path))
    s1 = Settings(_env_file=None)
    assert s1.jwt_secret_autogenerated and s1.JWT_SECRET_KEY != "change_this_to_a_secure_random_secret_in_production"
    assert (tmp_path / "jwt_secret.key").stat().st_mode & 0o077 == 0  # chỉ chủ sở hữu đọc được
    assert Settings(_env_file=None).JWT_SECRET_KEY == s1.JWT_SECRET_KEY  # ổn định qua các lần khởi động
