"""Chữ ký mù RSA theo chuẩn RFC 9474 — biến thể RSABSSA-SHA384-PSS-Deterministic.

Luồng (RFC 9474 §4):
  App      : encoded = EMSA-PSS-ENCODE(msg, modBits-1)   [SHA-384, MGF1-SHA384, salt 48 byte]
             m = OS2IP(encoded); r ngẫu nhiên; blinded = m · r^e mod n        -> gửi `blinded_hash`
  Server   : s* = blinded^d mod n  (kiểm tra s*^e == blinded để chống lỗi tính toán)  -> trả `blind_signature`
  App      : s = s* · r⁻¹ mod n; kiểm tra s^e == m                             -> gửi `unblinded_signature`
  Server   : xác minh `s` là chữ ký RSASSA-PSS CHUẨN của msg (thư viện `cryptography`).

`msg` = payload_message(...) — ràng buộc chuyên mục, nội dung đã mã hóa, mã hồ sơ, khóa hồ sơ và
mã băm từng tệp bằng chứng (xem docs/protocol.md). Phải khớp từng byte với RsaBlindClient (Android);
kiểm tra chéo bằng protocol/test_vectors.json.

Vì sao đổi từ RSA "trơn" (s^e == SHA256(...) mod n): RSA trơn có tính nhân (malleable) và giá trị băm
256 bit không phủ miền 2048 bit; RFC 9474 dùng mã hóa PSS ngẫu nhiên nên chữ ký cuối cùng là một
chữ ký RSA-PSS tiêu chuẩn, kiểm tra được bằng thư viện chuẩn.
"""
from __future__ import annotations

import hashlib
import math
import os
import secrets
from typing import List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.crypto.key_manager import key_manager

HASH_LEN = 48   # SHA-384
SALT_LEN = 48   # RSABSSA-SHA384-PSS: sLen = hLen


def parse_rsa_int(raw: str) -> int:
    """Đọc số nguyên lớn (chữ ký, giá trị làm mù) do client gửi lên.

    Chấp nhận: "0x..." (hex), chuỗi có chữ a-f (hex không tiền tố), hoặc chuỗi thập phân.
    Raises: ValueError nếu rỗng hoặc sai định dạng.
    """
    value = (raw or "").strip()
    if not value:
        raise ValueError("Giá trị số nguyên rỗng.")
    if value[:2].lower() == "0x" or any(c in "abcdefABCDEF" for c in value):
        return int(value, 16)
    return int(value)


def payload_message(
    category: str,
    encrypted_title: str,
    encrypted_description: str,
    case_token: str,
    case_public_key: str,
    evidence_file_hashes: List[str],
) -> bytes:
    """Thông điệp được ký mù: các trường (đã trim, UTF-8) nối bằng '|', mã băm tệp sắp tăng dần."""
    parts = [category, encrypted_title, encrypted_description, case_token, case_public_key]
    parts += sorted(h.strip() for h in evidence_file_hashes)
    return b"|".join(p.strip().encode("utf-8") for p in parts)


def _mgf1_sha384(seed: bytes, length: int) -> bytes:
    out, counter = b"", 0
    while len(out) < length:
        out += hashlib.sha384(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:length]


def emsa_pss_encode(msg: bytes, em_bits: int, salt: Optional[bytes] = None) -> bytes:
    """EMSA-PSS-ENCODE (RFC 8017 §9.1.1) với SHA-384 / MGF1-SHA384 / salt 48 byte."""
    em_len = (em_bits + 7) // 8
    if em_len < HASH_LEN + SALT_LEN + 2:
        raise ValueError("Khóa RSA quá ngắn cho PSS-SHA384")
    salt = os.urandom(SALT_LEN) if salt is None else salt
    if len(salt) != SALT_LEN:
        raise ValueError("Salt phải dài 48 byte")
    m_hash = hashlib.sha384(msg).digest()
    h = hashlib.sha384(b"\x00" * 8 + m_hash + salt).digest()
    db = b"\x00" * (em_len - SALT_LEN - HASH_LEN - 2) + b"\x01" + salt
    masked = bytearray(a ^ b for a, b in zip(db, _mgf1_sha384(h, em_len - HASH_LEN - 1)))
    masked[0] &= 0xFF >> (8 * em_len - em_bits)
    return bytes(masked) + h + b"\xbc"


def _k(n: int) -> int:
    return (n.bit_length() + 7) // 8


class BlindSignatureEngine:
    """Phía server (Ban Thanh tra): ký mù và xác minh chữ ký RFC 9474."""

    @staticmethod
    def blind_sign(blinded: int) -> int:
        """BlindSign (RFC 9474 §4.3): s* = blinded^d mod n, kèm kiểm tra s*^e == blinded."""
        d, n = key_manager.rsa_private_numbers
        e, _ = key_manager.rsa_public_numbers
        if blinded <= 1 or blinded >= n:
            raise ValueError("Giá trị làm mù không hợp lệ (ngoài khoảng 1 < m* < N).")
        s_star = pow(blinded, d, n)
        if pow(s_star, e, n) != blinded:  # chống lỗi tính toán làm lộ khóa riêng
            raise ValueError("Lỗi nội bộ khi ký.")
        return s_star

    @staticmethod
    def verify(msg: bytes, s: int, e: Optional[int] = None, n: Optional[int] = None) -> bool:
        """Xác minh `s` là chữ ký RSASSA-PSS (SHA-384, MGF1-SHA384, salt 48) hợp lệ của `msg`."""
        if e is None or n is None:
            e, n = key_manager.rsa_public_numbers
        if s <= 1 or s >= n:
            return False
        public_key = rsa.RSAPublicNumbers(e, n).public_key()
        try:
            public_key.verify(
                s.to_bytes(_k(n), "big"), msg,
                padding.PSS(mgf=padding.MGF1(hashes.SHA384()), salt_length=SALT_LEN),
                hashes.SHA384(),
            )
            return True
        except InvalidSignature:
            return False


# ---------------------------------------------------------------------------
# Phía client (dùng cho kiểm thử / mô phỏng; app Android có bản Kotlin tương đương)
# ---------------------------------------------------------------------------

def client_blind(msg: bytes, e: int, n: int, salt: Optional[bytes] = None,
                 r: Optional[int] = None) -> Tuple[int, int, int]:
    """Blind (RFC 9474 §4.2). Trả về (blinded, r, m) với m = OS2IP(EMSA-PSS-ENCODE(msg))."""
    m = int.from_bytes(emsa_pss_encode(msg, n.bit_length() - 1, salt), "big")
    if math.gcd(m, n) != 1:
        raise ValueError("Thông điệp không hợp lệ")
    while r is None or math.gcd(r, n) != 1:
        r = secrets.randbelow(n - 2) + 2
    return (m * pow(r, e, n)) % n, r, m


def client_finalize(s_star: int, r: int, m: int, e: int, n: int) -> int:
    """Finalize (RFC 9474 §4.4): bóc mù rồi kiểm tra chữ ký trước khi dùng."""
    s = (s_star * pow(r, -1, n)) % n
    if pow(s, e, n) != m:
        raise ValueError("Chữ ký mù trả về không hợp lệ")
    return s


def simulate_client_blinding(value: int, e: int, n: int) -> Tuple[int, int]:
    """Làm mù một số nguyên bất kỳ (chỉ dùng cho test hạn mức / tải, không phải luồng nộp hồ sơ)."""
    while True:
        r = secrets.randbelow(n - 2) + 2
        if math.gcd(r, n) == 1:
            break
    return (value * pow(r, e, n)) % n, r
