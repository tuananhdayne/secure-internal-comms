"""Sinh CA nội bộ + chứng chỉ TLS cho môi trường phát triển / demo.

Chạy (trong thư mục backend):
    python scripts/gen_dev_certs.py                 # SAN mặc định: localhost, 127.0.0.1, 10.0.2.2
    python scripts/gen_dev_certs.py 192.168.1.15    # thêm IP LAN để điện thoại thật kết nối

Kết quả:
    backend/certs/server.crt, backend/certs/server.key   -> dùng cho uvicorn (KHÔNG commit, đã .gitignore)
    backend/certs/ca.crt                                -> CA công khai (an toàn để chia sẻ)
    android/app/src/main/res/raw/atbm_dev_ca.pem        -> app Android chỉ tin CA này (network_security_config)

Khóa riêng của CA bị hủy ngay sau khi ký, nên không ai (kể cả máy dev) có thể ký thêm
chứng chỉ giả mạo bằng CA này. Muốn đổi SAN thì chạy lại script (sinh CA mới) và build lại app.
"""
from __future__ import annotations

import ipaddress
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

BACKEND_DIR = Path(__file__).resolve().parent.parent
CERTS_DIR = BACKEND_DIR / "certs"
ANDROID_RAW = BACKEND_DIR.parent / "android" / "app" / "src" / "main" / "res" / "raw"
DEFAULT_SANS = ["localhost", "127.0.0.1", "10.0.2.2"]


def _san_entries(names: list[str]) -> list[x509.GeneralName]:
    entries: list[x509.GeneralName] = []
    for name in dict.fromkeys(names):
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            entries.append(x509.DNSName(name))
    return entries


def main(extra: list[str]) -> None:
    now = datetime.now(timezone.utc)
    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. CA tự ký (ECDSA P-256), chỉ dùng để ký đúng 1 chứng chỉ server
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ATBM KMA Dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, "ATBM Dev Root CA"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=False, key_cert_sign=True, crl_sign=True,
                                     content_commitment=False, key_encipherment=False, data_encipherment=False,
                                     key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    # 2. Chứng chỉ server
    sans = DEFAULT_SANS + extra
    srv_key = ec.generate_private_key(ec.SECP256R1())
    srv_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, sans[0])]))
        .issuer_name(ca_name)
        .public_key(srv_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=397))
        .add_extension(x509.SubjectAlternativeName(_san_entries(sans)), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    del ca_key  # hủy khóa CA: không lưu ra đĩa

    pem = serialization.Encoding.PEM
    (CERTS_DIR / "ca.crt").write_bytes(ca_cert.public_bytes(pem))
    (CERTS_DIR / "server.crt").write_bytes(srv_cert.public_bytes(pem) + ca_cert.public_bytes(pem))
    key_path = CERTS_DIR / "server.key"
    key_path.write_bytes(srv_key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)

    if ANDROID_RAW.parent.exists():
        ANDROID_RAW.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CERTS_DIR / "ca.crt", ANDROID_RAW / "atbm_dev_ca.pem")
        print(f"[OK] Đã chép CA cho Android: {ANDROID_RAW / 'atbm_dev_ca.pem'}")

    print(f"[OK] Chứng chỉ server ({', '.join(sans)}) -> {CERTS_DIR}")
    print("     Chạy server: python run_https.py   (https://localhost:8443, emulator: https://10.0.2.2:8443)")


if __name__ == "__main__":
    main(sys.argv[1:])
