"""Sinh bộ dữ liệu kiểm thử DÙNG CHUNG cho server (Python) và app Android (Kotlin).

    python scripts/gen_protocol_vectors.py      # ghi đè protocol/test_vectors.json

Mục đích: giao thức nộp hồ sơ (thông điệp ký mù, RFC 9474 PSS, ECIES, ECDSA) phải khớp
từng byte giữa hai nền tảng. Cả tests/blackbox/test_protocol_vectors.py và
android/app/src/test/.../CryptoUnitTest.kt cùng đọc file JSON này; bên nào lệch là test báo ngay.

Chỉ dùng KHÓA THỬ sinh tại chỗ (không đụng khóa thật trong backend/keys). Chạy lại script sẽ tạo
khóa/ciphertext mới — chỉ cần chạy lại khi cố ý thay đổi giao thức (và commit file JSON mới).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec, rsa  # noqa: E402

from app.crypto.blind_signature import (  # noqa: E402
    BlindSignatureEngine, client_blind, client_finalize, emsa_pss_encode, payload_message,
)
from app.crypto.ecies import ecies_encrypt  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "protocol" / "test_vectors.json"


def main() -> None:
    # --- RSA thử cho chữ ký mù ---
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nums = rsa_key.private_numbers()
    n, e, d = nums.public_numbers.n, nums.public_numbers.e, nums.d

    msg_cases = []
    for case in [
        dict(name="cơ bản", category="Tham nhũng tài chính", encrypted_title="a1b2c3", encrypted_description="d4e5f6" * 8,
             case_token="CASE-" + "0f" * 16, case_public_key="04" + "ab" * 64,
             evidence_file_hashes=[hashlib.sha256(b"tep-2").hexdigest(), hashlib.sha256(b"tep-1").hexdigest()]),
        dict(name="khoảng trắng hai đầu + tiếng Việt (phải trim)", category="  Khác: Bắt nạt nơi làm việc ",
             encrypted_title=" aa ", encrypted_description="bb\n", case_token=" CASE-" + "1e" * 16 + " ",
             case_public_key="04" + "cd" * 64 + " ", evidence_file_hashes=[" " + hashlib.sha256(b"x").hexdigest()]),
        dict(name="không có tệp", category="Gian lận đấu thầu", encrypted_title="00", encrypted_description="11",
             case_token="CASE-" + "2d" * 16, case_public_key="04" + "ef" * 64, evidence_file_hashes=[]),
    ]:
        msg = payload_message(case["category"], case["encrypted_title"], case["encrypted_description"],
                              case["case_token"], case["case_public_key"], case["evidence_file_hashes"])
        msg_cases.append({**case, "expected_message_hex": msg.hex()})

    # --- RFC 9474 (RSABSSA-SHA384-PSS-Deterministic) với salt + r cố định để so khớp từng byte ---
    msg = bytes.fromhex(msg_cases[0]["expected_message_hex"])
    salt = secrets.token_bytes(48)
    encoded = emsa_pss_encode(msg, n.bit_length() - 1, salt)
    blinded, r, m = client_blind(msg, e, n, salt=salt)
    s_star = pow(blinded, d, n)
    s = client_finalize(s_star, r, m, e, n)
    assert BlindSignatureEngine.verify(msg, s, e, n)

    # --- ECIES: server mã hóa, app giải mã (cùng HKDF/AES-GCM) ---
    ec_key = ec.generate_private_key(ec.SECP256R1())
    pkcs8_hex = ec_key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()).hex()
    pub_hex = ec_key.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint).hex()
    plaintexts = ["Tiêu đề|||Mô tả chi tiết có dấu tiếng Việt", "", "x" * 1000]
    ecies_cases = [{"plaintext_utf8": p, **ecies_encrypt(pub_hex, p.encode("utf-8"))} for p in plaintexts]

    # --- ECDSA (SHA256withECDSA, DER) trên chuỗi ciphertext hex của tin nhắn ---
    message = ecies_cases[0]["ciphertext"]
    signature = ec_key.sign(message.encode("utf-8"), ec.ECDSA(hashes.SHA256())).hex()

    data = {
        "_note": "Sinh bởi backend/scripts/gen_protocol_vectors.py — KHÓA THỬ, không dùng cho hệ thống thật.",
        "payload_message": {"cases": msg_cases},
        "blind_signature": {
            "scheme": "RFC 9474 RSABSSA-SHA384-PSS-Deterministic",
            "n_hex": format(n, "x"), "e_hex": format(e, "x"),
            "message_hex": msg.hex(), "salt_hex": salt.hex(), "encoded_message_hex": encoded.hex(),
            "r_hex": format(r, "x"), "blinded_hex": format(blinded, "x"),
            "blind_signature_hex": format(s_star, "x"), "signature_hex": format(s, "x"),
        },
        "ecies": {"recipient_private_pkcs8_hex": pkcs8_hex, "recipient_public_hex": pub_hex,
                  "hkdf_info": "atbm-ecies-aes256gcm", "cases": ecies_cases},
        "ecdsa": {"public_hex": pub_hex, "private_pkcs8_hex": pkcs8_hex, "message_utf8": message,
                  "signature_der_hex": signature},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUT}")


if __name__ == "__main__":
    main()
