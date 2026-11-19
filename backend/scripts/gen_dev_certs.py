"""Sinh / tái sử dụng CA nội bộ + cấp chứng chỉ TLS server cho môi trường phát triển / demo.

Chạy (trong thư mục backend):
    python scripts/gen_dev_certs.py                 # SAN mặc định: localhost, 127.0.0.1, 10.0.2.2
    python scripts/gen_dev_certs.py 192.168.1.15    # thêm IP LAN để điện thoại thật kết nối
    python scripts/gen_dev_certs.py --new-ca ...    # BẮT BUỘC sinh CA mới (phải cài lại mọi APK)

Kết quả:
    backend/certs/ca.key                            -> khóa riêng CA dev (quyền 600, KHÔNG commit)
    backend/certs/ca.crt                            -> CA công khai (an toàn để chia sẻ)
    backend/certs/server.crt, backend/certs/server.key -> dùng cho uvicorn (KHÔNG commit)
    android/app/src/main/res/raw/atbm_dev_ca.pem    -> CA mà app Android tin (network_security_config)

Mô hình tin cậy:
    - Đây là CA CHỈ DÙNG CHO PHÁT TRIỂN. Khóa riêng của CA nằm lại trên máy dev, trong
      backend/certs/ (đã có trong .gitignore), không bao giờ rời máy và không đi vào APK.
    - CA được giữ ổn định qua các lần chạy: khi đổi mạng Wi-Fi / đổi IP chỉ cần cấp lại
      chứng chỉ server (leaf) mang IP mới, APK đã cài vẫn tin được -> chỉ cài APK MỘT lần.
    - Bản debug tin CA này cho mọi host (để thử qua LAN); mọi bản build (kể cả release) chỉ
      tin CA này cho 10.0.2.2 / localhost / 127.0.0.1. Máy chủ thật dùng chứng chỉ công khai.
    - --new-ca sinh CA mới và ghi đè ca.key: mọi APK đã cài sẽ không kết nối được nữa
      cho tới khi build + cài lại.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

BACKEND_DIR = Path(__file__).resolve().parent.parent
CERTS_DIR = BACKEND_DIR / "certs"
CA_KEY_PATH = CERTS_DIR / "ca.key"
CA_CRT_PATH = CERTS_DIR / "ca.crt"
ANDROID_RAW = BACKEND_DIR.parent / "android" / "app" / "src" / "main" / "res" / "raw"
ANDROID_CA_PATH = ANDROID_RAW / "atbm_dev_ca.pem"
DEFAULT_SANS = ["localhost", "127.0.0.1", "10.0.2.2"]
PEM = serialization.Encoding.PEM


def _write_private(path: Path, data: bytes) -> None:
    """Ghi khóa riêng với quyền 600 ngay từ lúc tạo file (không có khoảnh khắc file đọc được)."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(path, 0o600)  # file cũ có thể đã tồn tại với quyền rộng hơn


def _key_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _san_entries(names: list[str]) -> list[x509.GeneralName]:
    entries: list[x509.GeneralName] = []
    for name in dict.fromkeys(names):
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            entries.append(x509.DNSName(name))
    return entries


def _new_ca(now: datetime) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    """CA tự ký (ECDSA P-256), lưu ca.key (600) + ca.crt."""
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
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=False, key_cert_sign=True, crl_sign=True,
                                     content_commitment=False, key_encipherment=False, data_encipherment=False,
                                     key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _write_private(CA_KEY_PATH, _key_pem(ca_key))
    CA_CRT_PATH.write_bytes(ca_cert.public_bytes(PEM))
    return ca_key, ca_cert


def _load_ca(now: datetime) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate] | None:
    """Nạp CA đã có; trả None nếu thiếu file, hỏng, khóa không khớp hoặc CA đã hết hạn."""
    if not (CA_KEY_PATH.exists() and CA_CRT_PATH.exists()):
        return None
    try:
        key = serialization.load_pem_private_key(CA_KEY_PATH.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(CA_CRT_PATH.read_bytes())
    except (ValueError, TypeError) as exc:
        print(f"[!] Không đọc được CA cũ ({type(exc).__name__}) -> sinh CA mới")
        return None
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.public_key() != cert.public_key():
        print("[!] ca.key không khớp ca.crt -> sinh CA mới")
        return None
    if cert.not_valid_after_utc <= now + timedelta(days=1):
        print("[!] CA cũ đã/sắp hết hạn -> sinh CA mới")
        return None
    CA_KEY_PATH.chmod(0o600)
    return key, cert


def _issue_server_cert(ca_key: ec.EllipticCurvePrivateKey, ca_cert: x509.Certificate,
                       sans: list[str], now: datetime) -> None:
    srv_key = ec.generate_private_key(ec.SECP256R1())
    srv_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, sans[0])]))
        .issuer_name(ca_cert.subject)
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
    _write_private(CERTS_DIR / "server.key", _key_pem(srv_key))
    (CERTS_DIR / "server.crt").write_bytes(srv_cert.public_bytes(PEM) + ca_cert.public_bytes(PEM))


def _sync_android_ca(ca_pem: bytes) -> bool:
    """Chép CA sang res/raw của Android khi khác nội dung. Trả True nếu đã ghi."""
    if not ANDROID_RAW.parent.exists():
        return False
    if ANDROID_CA_PATH.exists() and ANDROID_CA_PATH.read_bytes() == ca_pem:
        return False
    ANDROID_RAW.mkdir(parents=True, exist_ok=True)
    ANDROID_CA_PATH.write_bytes(ca_pem)
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CA dev ổn định + cấp chứng chỉ server TLS.")
    parser.add_argument("sans", nargs="*", help="IP/tên miền thêm vào SAN (vd. IP LAN của máy)")
    parser.add_argument("--new-ca", action="store_true",
                        help="Bắt buộc sinh CA mới (mọi APK đã cài phải cài lại)")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CERTS_DIR, 0o700)

    loaded = None if args.new_ca else _load_ca(now)
    if loaded is None:
        ca_key, ca_cert = _new_ca(now)
        print("[OK] Đã sinh CA dev MỚI -> backend/certs/ca.key (600), ca.crt")
        print("[!]  CA đã đổi: mọi APK đã cài phải build + cài lại (./dev.sh apk).")
    else:
        ca_key, ca_cert = loaded
        print("[OK] Dùng lại CA dev có sẵn (APK đã cài vẫn kết nối được)")

    sans = DEFAULT_SANS + list(args.sans)
    _issue_server_cert(ca_key, ca_cert, sans, now)

    if _sync_android_ca(ca_cert.public_bytes(PEM)):
        print(f"[OK] Đã chép CA cho Android: {ANDROID_CA_PATH}")

    print(f"[OK] Chứng chỉ server ({', '.join(dict.fromkeys(sans))}) -> {CERTS_DIR}")
    print("     Chạy server: python run_https.py   (https://localhost:8443, emulator: https://10.0.2.2:8443)")


if __name__ == "__main__":
    main()
