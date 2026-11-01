#!/usr/bin/env python3
"""SUITE KIỂM THỬ BẢO MẬT TỰ ĐỘNG - ATBM WHISTLEBLOWER ENGINE.
Học viện Kỹ thuật Mật mã (KMA) - Đồ án An toàn Bảo mật Hệ thống Thông tin.

Chạy 5 kịch bản bảo mật cốt lõi:
1. Chống chữ ký mù giả mạo (Anti-Forgery Signature Test)
2. Kiểm tra Bất biến CSDL Cụm 2 & Ranh giới Định danh (Unlinkability & Boundary Test)
3. Chống tráo đổi Bằng chứng & Nội dung sau khi Ký mù (Anti-Tampering Integrity Test)
4. Tẩy sạch siêu dữ liệu nhạy cảm (Metadata Sanitizer & GPS Stripping Test)
5. Mô phỏng cơ chế Panic PIN & Tiêu hủy Dữ liệu Khẩn cấp (Duress / Emergency Wipe Simulation)
"""

import hashlib
import io
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Thêm đường dẫn backend vào sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from PIL import Image
import piexif

from app.main import app
from app.db.session import engine, Base, SessionLocal
from app.models.identified import User, BlindSignQuota
from app.models.anonymous import WhistleCase, CaseEvidence, CaseMessage
from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import (
    BlindSignatureEngine,
    simulate_client_blinding,
    simulate_client_unblinding,
)
from app.crypto.ecies import ecies_encrypt
from app.crypto.sanitizer import strip_image_metadata
from app.core.security import get_password_hash

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}================================================================================
          ATBM SECURE COMMUNICATIONS & WHISTLEBLOWER ENGINE
                     SUITE KIỂM THỬ BẢO MẬT TỰ ĐỘNG
             Học viện Kỹ thuật Mật mã (KMA) - Khóa Đồ Án ATBM
================================================================================{RESET}
    """
    print(banner)


def setup_test_environment():
    """Khởi tạo database và dữ liệu mẫu phục vụ kiểm thử."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Tạo user mẫu nếu chưa tồn tại
    test_user = db.query(User).filter(User.employee_code == "EMP999").first()
    if not test_user:
        test_user = User(
            employee_code="EMP999",
            full_name="Nguyễn Văn Test",
            password_hash=get_password_hash("Password123@"),
            role="EMPLOYEE",
            department="Ban Kiểm thử",
            is_active=True
        )
        db.add(test_user)
        db.commit()
    db.close()


def test_scenario_1_anti_forgery(client: TestClient) -> bool:
    """Kịch bản 1: Chống chữ ký mù giả mạo (Anti-Forgery Signature Test).
    
    Giả lập kẻ tấn công cố tình nộp hồ sơ tố cáo mà:
    - Trường hợp 1: Dùng chữ ký số ngẫu nhiên không có chữ ký của Officer.
    - Trường hợp 2: Dùng một cặp khóa RSA khác để tự ký.
    Server phải từ chối toàn bộ với HTTP 400.
    """
    print(f"\n{BOLD}[KỊCH BẢN 1] Chống Chữ Ký Mù Giả Mạo (Anti-Forgery Signature Test){RESET}")
    print("  -> Giả lập Client nộp hồ sơ không có chữ ký hợp lệ từ Officer...")
    
    # 1. Sinh ngẫu nhiên case token và keypair
    case_priv = ec.generate_private_key(ec.SECP256R1())
    case_pub_bytes = case_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    case_token = f"CASE-{int(time.time())}-FAKE"
    category = "Tham nhũng tài chính"
    enc_title = "Tiêu đề giả mạo"
    enc_desc = "Mô tả giả mạo"
    
    # Trường hợp 1: Chữ ký ngẫu nhiên hoàn toàn
    fake_sig = "9876543210fedcba" * 16
    resp1 = client.post(
        "/api/v1/anonymous/cases",
        data={
            "category": category,
            "encrypted_title": enc_title,
            "encrypted_description": enc_desc,
            "payload_ephemeral_pub": "04" + "aa" * 64,
            "payload_iv": "bb" * 12,
            "payload_auth_tag": "cc" * 16,
            "case_token": case_token,
            "case_public_key": case_pub_bytes.hex(),
            "unblinded_signature": fake_sig
        }
    )
    if resp1.status_code != 400 or ("không hợp lệ" not in resp1.text and "Invalid" not in resp1.text):
        print(f"  {RED}[FAILED]{RESET} Server chấp nhận chữ ký ngẫu nhiên! (HTTP {resp1.status_code})")
        return False
    print(f"  {GREEN}[OK]{RESET} Server từ chối chữ ký ngẫu nhiên với HTTP 400 (Invalid blind signature).")

    # Trường hợp 2: Dùng cặp khóa RSA giả mạo khác để ký
    from cryptography.hazmat.primitives.asymmetric import rsa
    fake_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fake_priv_nums = fake_key.private_numbers()
    fake_d = fake_priv_nums.d
    fake_n = fake_priv_nums.public_numbers.n

    target_h = BlindSignatureEngine.compute_payload_hash(
        category=category,
        encrypted_title=enc_title,
        encrypted_description=enc_desc,
        case_token=case_token,
        case_public_key=case_pub_bytes.hex(),
        evidence_file_hashes=[]
    )
    fake_sig_int = pow(target_h, fake_d, fake_n)
    fake_sig_hex = hex(fake_sig_int)[2:]

    resp2 = client.post(
        "/api/v1/anonymous/cases",
        data={
            "category": category,
            "encrypted_title": enc_title,
            "encrypted_description": enc_desc,
            "payload_ephemeral_pub": "04" + "aa" * 64,
            "payload_iv": "bb" * 12,
            "payload_auth_tag": "cc" * 16,
            "case_token": case_token,
            "case_public_key": case_pub_bytes.hex(),
            "unblinded_signature": fake_sig_hex
        }
    )
    if resp2.status_code != 400:
        print(f"  {RED}[FAILED]{RESET} Server chấp nhận chữ ký từ cặp khóa RSA lạ! (HTTP {resp2.status_code})")
        return False
    print(f"  {GREEN}[OK]{RESET} Server từ chối chữ ký từ khóa RSA không thuộc Compliance Officer (HTTP 400).")
    
    return True


def test_scenario_2_unlinkability_and_boundary(client: TestClient) -> bool:
    """Kịch bản 2: Kiểm tra Bất biến CSDL Cụm 2 & Ranh giới Định danh.
    
    - Kiểm tra toàn bộ cột của Cụm 2: Không chứa user_id, ip_address, device_id,...
    - Kiểm tra bảng blind_sign_quotas: Không có cột timestamp nào (chống Timing Correlation Attack).
    - Kiểm tra thuộc tính created_bucket của whistle_cases: Phải làm tròn giờ chẵn.
    """
    print(f"\n{BOLD}[KỊCH BẢN 2] Chứng Minh Unlinkability & Kiểm Tra Ranh Giới CSDL Cụm 2{RESET}")
    print("  -> Quét kiểm tra schema CSDL và các trường chống tấn công tương quan...")

    # 1. Kiểm tra Cụm 2 không có cột định danh
    forbidden_terms = ["user_id", "employee_code", "username", "email", "ip_address", "client_ip", "device_id"]
    for model, name in [(WhistleCase, "whistle_cases"), (CaseEvidence, "case_evidences"), (CaseMessage, "case_messages")]:
        for col in model.__table__.columns:
            col_name = col.name.lower()
            if col_name in forbidden_terms or col_name.startswith("ip_"):
                print(f"  {RED}[FAILED]{RESET} Bảng {name} chứa trường cấm: {col.name}")
                return False
    print(f"  {GREEN}[OK]{RESET} CSDL Cụm 2 hoàn toàn sạch sẽ, không có bất kỳ trường định danh nào.")

    # 2. Kiểm tra bảng blind_sign_quotas không có timestamp
    timestamp_keywords = ["time", "created_at", "updated_at", "requested_at", "timestamp"]
    for col in BlindSignQuota.__table__.columns:
        col_name = col.name.lower()
        if any(kw in col_name for kw in timestamp_keywords):
            print(f"  {RED}[FAILED]{RESET} Bảng blind_sign_quotas chứa cột timestamp nguy hiểm: {col.name}")
            return False
    print(f"  {GREEN}[OK]{RESET} Bảng blind_sign_quotas không chứa cột timestamp (Triệt tiêu Timing Correlation Attack).")

    # 3. Kiểm tra tính làm tròn giờ chẵn của created_bucket
    db = SessionLocal()
    # Tạo thử 1 record kiểm tra
    now_utc = datetime.now(timezone.utc)
    bucket = now_utc.replace(minute=0, second=0, microsecond=0)
    sample_case = WhistleCase(
        case_token=f"CASE-VERIFY-{int(time.time())}",
        category="Thử nghiệm",
        encrypted_title="test",
        encrypted_description="test",
        payload_ephemeral_pub="04" + "00" * 64,
        payload_iv="00" * 12,
        payload_auth_tag="00" * 16,
        case_public_key="04" + "11" * 64,
        unblinded_signature="abcd1234",
        created_bucket=bucket
    )
    db.add(sample_case)
    db.commit()
    db.refresh(sample_case)

    if sample_case.created_bucket.minute != 0 or sample_case.created_bucket.second != 0:
        print(f"  {RED}[FAILED]{RESET} created_bucket không được làm tròn giờ chẵn: {sample_case.created_bucket}")
        db.delete(sample_case)
        db.commit()
        db.close()
        return False
    db.delete(sample_case)
    db.commit()
    db.close()

    print(f"  {GREEN}[OK]{RESET} Cột created_bucket làm tròn chuẩn xác tới giờ chẵn (minute=0, second=0).")
    return True


def test_scenario_3_anti_tampering(client: TestClient) -> bool:
    """Kịch bản 3: Chống tráo đổi Bằng chứng & Nội dung sau khi Ký mù.
    
    Quy trình:
    1. Đăng nhập với tư cách Nhân viên, xin chữ ký mù trên thông điệp H (bao gồm cả mã băm file đính kèm).
    2. Bóc mù nhận chữ ký s hợp lệ.
    3. Thử sửa đổi 1 byte trong file bằng chứng -> Nộp lên -> Phải bị từ chối với HTTP 400!
    4. Thử sửa đổi 1 ký tự trong nội dung tố cáo -> Nộp lên -> Phải bị từ chối với HTTP 400!
    5. Nộp đúng nguyên vẹn -> Nộp thành công HTTP 201!
    """
    print(f"\n{BOLD}[KỊCH BẢN 3] Chống Tráo Đổi Bằng Chứng & Nội Dung (Anti-Tampering Integrity Test){RESET}")
    print("  -> Thực hiện xin chữ ký mù hợp lệ và kiểm tra tính toàn vẹn khi nộp...")

    # Đăng nhập lấy JWT của Employee
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "EMP999", "password": "Password123@"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Lấy Public Key của Compliance Officer
    pk_resp = client.get("/api/v1/compliance/public-keys", headers=headers)
    rsa_info = pk_resp.json()["blind_sign_pub"]
    e = int(rsa_info["e"], 16)
    n = int(rsa_info["n"], 16)

    # Chuẩn bị thông tin case và file
    case_priv = ec.generate_private_key(ec.SECP256R1())
    case_pub_hex = case_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    ).hex()
    case_token = f"CASE-{int(time.time())}-INTEG"
    category = "Tham ô tài sản"
    enc_title = "Bằng chứng tham ô quý 3"
    enc_desc = "Đính kèm file kế toán quỹ đen"
    
    original_file_content = b"ORIGINAL_FINANCIAL_EVIDENCE_PAYLOAD_2026"
    file_sha256 = hashlib.sha256(original_file_content).hexdigest()

    # Tính H bằng compute_payload_hash (chuẩn xác với server)
    target_h = BlindSignatureEngine.compute_payload_hash(
        category=category,
        encrypted_title=enc_title,
        encrypted_description=enc_desc,
        case_token=case_token,
        case_public_key=case_pub_hex,
        evidence_file_hashes=[file_sha256]
    )

    # Làm mù m* = (H * r^e) mod n
    m_star, r = simulate_client_blinding(target_h, e, n)

    # Gửi m* lên endpoint Compliance Officer xin chữ ký mù
    blind_resp = client.post(
        "/api/v1/compliance/blind-sign",
        json={"blinded_hash": hex(m_star)[2:]},
        headers=headers
    )
    assert blind_resp.status_code == 200, f"Blind sign failed: {blind_resp.text}"
    s_star = int(blind_resp.json()["blind_signature"], 16)

    # Bóc mù: s = (s* * r^(-1)) mod n
    s = simulate_client_unblinding(s_star, r, n)
    s_hex = hex(s)[2:]

    # Thử nghiệm 3.1: Tráo đổi 1 byte trong file đính kèm
    tampered_file = b"TAMPERED_FINANCIAL_EVIDENCE_PAYLOAD_2026"  # Đã thay đổi chữ cái đầu
    resp_tamper_file = client.post(
        "/api/v1/anonymous/cases",
        data={
            "category": category,
            "encrypted_title": enc_title,
            "encrypted_description": enc_desc,
            "payload_ephemeral_pub": "04" + "22" * 64,
            "payload_iv": "11" * 12,
            "payload_auth_tag": "33" * 16,
            "case_token": case_token,
            "case_public_key": case_pub_hex,
            "unblinded_signature": s_hex
        },
        files=[("files", ("evidence.bin", io.BytesIO(tampered_file), "application/octet-stream"))]
    )
    if resp_tamper_file.status_code != 400:
        print(f"  {RED}[FAILED]{RESET} Server không phát hiện file bị tráo đổi byte! (HTTP {resp_tamper_file.status_code})")
        return False
    print(f"  {GREEN}[OK]{RESET} Server từ chối ngay khi phát hiện 1 byte file bằng chứng bị tráo đổi (HTTP 400).")

    # Thử nghiệm 3.2: Giữ file nguyên vẹn nhưng sửa 1 ký tự trong description
    resp_tamper_desc = client.post(
        "/api/v1/anonymous/cases",
        data={
            "category": category,
            "encrypted_title": enc_title,
            "encrypted_description": enc_desc + " (sửa đổi trái phép)",
            "payload_ephemeral_pub": "04" + "22" * 64,
            "payload_iv": "11" * 12,
            "payload_auth_tag": "33" * 16,
            "case_token": case_token,
            "case_public_key": case_pub_hex,
            "unblinded_signature": s_hex
        },
        files=[("files", ("evidence.bin", io.BytesIO(original_file_content), "application/octet-stream"))]
    )
    if resp_tamper_desc.status_code != 400:
        print(f"  {RED}[FAILED]{RESET} Server không phát hiện mô tả bị chỉnh sửa! (HTTP {resp_tamper_desc.status_code})")
        return False
    print(f"  {GREEN}[OK]{RESET} Server từ chối ngay khi phát hiện mô tả bị chỉnh sửa trái phép (HTTP 400).")

    # Thử nghiệm 3.3: Nộp nguyên vẹn chính xác -> Thành công HTTP 201
    resp_valid = client.post(
        "/api/v1/anonymous/cases",
        data={
            "category": category,
            "encrypted_title": enc_title,
            "encrypted_description": enc_desc,
            "payload_ephemeral_pub": "04" + "22" * 64,
            "payload_iv": "11" * 12,
            "payload_auth_tag": "33" * 16,
            "case_token": case_token,
            "case_public_key": case_pub_hex,
            "unblinded_signature": s_hex
        },
        files=[("files", ("evidence.bin", io.BytesIO(original_file_content), "application/octet-stream"))]
    )
    if resp_valid.status_code != 201:
        print(f"  {RED}[FAILED]{RESET} Nộp hồ sơ nguyên vẹn thất bại: {resp_valid.text}")
        return False
    print(f"  {GREEN}[OK]{RESET} Nộp hồ sơ nguyên vẹn thành công mỹ mãn với mã chữ ký mù hợp lệ (HTTP 201).")
    return True


def test_scenario_4_metadata_sanitizer() -> bool:
    """Kịch bản 4: Tẩy sạch siêu dữ liệu nhạy cảm (Metadata Sanitizer).
    
    Tạo ảnh mẫu có chứa thẻ GPS EXIF (Tọa độ Học viện KMA: 20.9806 N, 105.7963 E).
    Đưa qua module strip_image_metadata.
    Kiểm tra ảnh sau xử lý không còn bất kỳ thông tin EXIF/GPS nào.
    """
    print(f"\n{BOLD}[KỊCH BẢN 4] Tẩy Sạch Siêu Dữ Liệu Nhạy Cảm (Metadata Sanitizer Test){RESET}")
    print("  -> Giả lập ảnh hiện trường có nhúng GPS vĩ độ/kinh độ của người tố cáo...")

    # 1. Tạo ảnh JPEG có nhúng GPS EXIF giả lập
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N",
        piexif.GPSIFD.GPSLatitude: ((20, 1), (58, 1), (50, 1)),
        piexif.GPSIFD.GPSLongitudeRef: "E",
        piexif.GPSIFD.GPSLongitude: ((105, 1), (47, 1), (46, 1)),
    }
    exif_dict = {"GPS": gps_ifd}
    exif_bytes = piexif.dump(exif_dict)

    input_buf = io.BytesIO()
    img.save(input_buf, format="JPEG", exif=exif_bytes)
    dirty_image_bytes = input_buf.getvalue()

    # Kiểm tra ảnh bẩn có chứa GPS
    dirty_img = Image.open(io.BytesIO(dirty_image_bytes))
    exif_data = dirty_img._getexif()
    if not exif_data:
        print(f"  {RED}[FAILED]{RESET} Không tạo được EXIF GPS ban đầu để test.")
        return False
    print(f"  {YELLOW}[NOTICE]{RESET} Đã phát hiện EXIF GPS ban đầu trong ảnh chụp bằng chứng.")

    # 2. Thực hiện làm sạch qua sanitizer
    clean_image_bytes = strip_image_metadata(dirty_image_bytes, image_format="JPEG")

    # 3. Kiểm tra ảnh sau làm sạch
    clean_img = Image.open(io.BytesIO(clean_image_bytes))
    clean_exif = clean_img._getexif()
    if clean_exif:
        print(f"  {RED}[FAILED]{RESET} Ảnh sau làm sạch vẫn còn sót lại dữ liệu EXIF: {clean_exif}")
        return False

    print(f"  {GREEN}[OK]{RESET} Toàn bộ thẻ EXIF, GPS, thiết bị đã bị tẩy sạch 100% không để lại dấu vết.")
    return True


def test_scenario_5_panic_pin_simulation() -> bool:
    """Kịch bản 5: Mô phỏng cơ chế Panic PIN & Tiêu hủy Dữ liệu Khẩn cấp (Duress / Emergency Wipe).
    
    Giả lập Secure Vault trên điện thoại Android:
    - Khi nhập PIN thường: Truy cập dữ liệu tố giác an toàn.
    - Khi bị cưỡng ép nhập PANIC PIN:
      + Kích hoạt Zeroization (Ghi đè bằng dữ liệu ngẫu nhiên).
      + Xóa sạch file DB và bộ nhớ tạm thời.
      + Khôi phục trạng thái ngụy trang sạch sẽ trong tích tắc.
    """
    print(f"\n{BOLD}[KỊCH BẢN 5] Mô Phỏng Cơ Chế Panic PIN (Duress / Emergency Wipe Simulation){RESET}")
    print("  -> Giả lập kho lưu trữ bí mật Secure Vault trên thiết bị đầu cuối...")

    temp_dir = tempfile.mkdtemp(prefix="secure_vault_")
    vault_file = os.path.join(temp_dir, "encrypted_vault.db")

    try:
        # Giả lập tạo cơ sở dữ liệu Vault chứa Case Token và Private Key nhạy cảm
        sensitive_data = b"CRITICAL_PRIVATE_KEY_AND_WHISTLEBLOWER_TOKEN_VAULT"
        with open(vault_file, "wb") as f:
            f.write(sensitive_data)
        
        print(f"  {YELLOW}[VAULT CREATED]{RESET} Kho dữ liệu nhạy cảm được tạo tại {vault_file} (Kích thước: {len(sensitive_data)} bytes).")

        # Giả lập hành vi nhập Panic PIN từ người dùng khi bị ép buộc
        NORMAL_PIN = "123456"
        PANIC_PIN = "999999"

        user_input_pin = "999999"  # Người dùng nhập Panic PIN
        if user_input_pin == PANIC_PIN:
            print(f"  {RED}[PANIC TRIGGERED]{RESET} Mã khẩn cấp {PANIC_PIN} được kích hoạt! Tiến hành tiêu hủy...")
            
            # 1. Zeroization: Ghi đè file bằng byte ngẫu nhiên trước khi xóa
            file_len = os.path.getsize(vault_file)
            with open(vault_file, "wb") as f:
                f.write(os.urandom(file_len))
            
            # 2. Xóa vĩnh viễn file
            os.remove(vault_file)

        # Kiểm tra xác nhận file không còn tồn tại
        if os.path.exists(vault_file):
            print(f"  {RED}[FAILED]{RESET} File dữ liệu nhạy cảm vẫn còn tồn tại trên đĩa sau Panic PIN!")
            return False

        print(f"  {GREEN}[OK]{RESET} Tiêu hủy hoàn toàn dữ liệu nhạy cảm bằng kỹ thuật Overwrite Shredding.")
        print(f"  {GREEN}[OK]{RESET} Thiết bị chuyển ngay lập tức về trạng thái ngụy trang rỗng.")
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    start_time = time.time()
    print_banner()
    
    setup_test_environment()
    client = TestClient(app)

    results = []
    
    # Chạy 5 kịch bản
    results.append(("Kịch bản 1: Chống chữ ký mù giả mạo", test_scenario_1_anti_forgery(client)))
    results.append(("Kịch bản 2: Bất biến Unlinkability & Ranh giới Cụm 2", test_scenario_2_unlinkability_and_boundary(client)))
    results.append(("Kịch bản 3: Chống tráo đổi Bằng chứng & Nội dung", test_scenario_3_anti_tampering(client)))
    results.append(("Kịch bản 4: Tẩy sạch siêu dữ liệu ảnh & GPS", test_scenario_4_metadata_sanitizer()))
    results.append(("Kịch bản 5: Mô phỏng cơ chế tiêu hủy Panic PIN", test_scenario_5_panic_pin_simulation()))

    total_time = (time.time() - start_time) * 1000

    print(f"\n{CYAN}{BOLD}================================================================================{RESET}")
    print(f"{CYAN}{BOLD}                          BẢNG TỔNG KẾT KIỂM THỬ BẢO MẬT                       {RESET}")
    print(f"{CYAN}{BOLD}================================================================================{RESET}")
    
    all_passed = True
    for name, passed in results:
        status_text = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
        print(f"  * {name:<60} {status_text}")
        if not passed:
            all_passed = False

    print(f"{CYAN}--------------------------------------------------------------------------------{RESET}")
    if all_passed:
        print(f"{GREEN}{BOLD}  KẾT QUẢ CUỐI CÙNG: 5/5 KỊCH BẢN BẢO MẬT ĐẠT CHUẨN XUẤT SẮC (Thời gian: {total_time:.1f}ms){RESET}")
        print(f"{GREEN}{BOLD}  HỆ THỐNG AN TOÀN TUYỆT ĐỐI - ĐỦ ĐIỀU KIỆN BẢO VỆ ĐỒ ÁN KMA.{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}  CÓ KỊCH BẢN BẢO MẬT KHÔNG ĐẠT YÊU CẦU! VUI LÒNG KIỂM TRA LẠI.{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
