"""White-Box Unit Tests: Cryptographic Primitives & Control-Flow Branch Coverage.

Kiểm thử Hộp trắng (White-Box Testing) cho tầng mật mã (`app/crypto/`):
- Bao phủ câu lệnh (Statement Coverage) & Bao phủ nhánh (Branch/Decision Coverage)
- Kiểm tra các điều kiện biên nội bộ của toán học RSA Blind Signature (m* <= 1, m* >= N, s <= 1, s >= N)
- Kiểm tra tính bất biến thứ tự file băm trong compute_payload_hash
- Kiểm tra các nhánh chuyển đổi hệ màu (RGB vs RGBA/P) và lột sạch EXIF trong strip_image_metadata
"""

import io
import math
import pytest
from PIL import Image
import piexif

from app.crypto.blind_signature import (
    BlindSignatureEngine,
    simulate_client_blinding,
    simulate_client_unblinding,
)
from app.crypto.key_manager import key_manager
from app.crypto.sanitizer import strip_image_metadata


def test_blind_sign_boundary_branches_raise_value_error() -> None:
    """WB-CRYPTO-01: Kiểm thử nhánh điều kiện biên `if m_star <= 1 or m_star >= n` trong blind_sign()."""
    _, n = key_manager.rsa_public_numbers

    for invalid_m_star in [0, 1, -5, n, n + 1]:
        with pytest.raises(ValueError, match="ngoài khoảng"):
            BlindSignatureEngine.blind_sign(invalid_m_star)


def test_verify_boundary_branches_return_false() -> None:
    """WB-CRYPTO-02: Kiểm thử nhánh điều kiện biên `if s <= 1 or s >= n` trong verify()."""
    _, n = key_manager.rsa_public_numbers
    valid_h = 123456789

    for invalid_s in [0, 1, -10, n, n + 100]:
        assert BlindSignatureEngine.verify(valid_h, invalid_s) is False


def test_compute_payload_hash_order_invariance_and_field_sensitivity() -> None:
    """WB-CRYPTO-03: Kiểm thử vòng lặp sorted(evidence_file_hashes) và độ nhạy từng trường."""
    h1 = BlindSignatureEngine.compute_payload_hash(
        category="CatA",
        encrypted_title="TitleA",
        encrypted_description="DescA",
        case_token="CASE-WB-01",
        case_public_key="04" + "aa" * 64,
        evidence_file_hashes=["hash_b", "hash_a", "hash_c"],
    )
    h2 = BlindSignatureEngine.compute_payload_hash(
        category="CatA",
        encrypted_title="TitleA",
        encrypted_description="DescA",
        case_token="CASE-WB-01",
        case_public_key="04" + "aa" * 64,
        evidence_file_hashes=["hash_a", "hash_c", "hash_b"],
    )
    # Thứ tự danh sách file băm khác nhau nhưng tập hợp giống nhau -> H phải trùng khớp
    assert h1 == h2

    # Thay đổi bất kỳ 1 trường nào cũng phải tạo ra H hoàn toàn khác (Avalanche effect)
    h_diff_cat = BlindSignatureEngine.compute_payload_hash(
        category="CatB",
        encrypted_title="TitleA",
        encrypted_description="DescA",
        case_token="CASE-WB-01",
        case_public_key="04" + "aa" * 64,
        evidence_file_hashes=["hash_a", "hash_b", "hash_c"],
    )
    assert h1 != h_diff_cat


def test_client_blinding_coprime_and_full_cycle() -> None:
    """WB-CRYPTO-04: Kiểm thử bất biến gcd(r, N) == 1 và chu trình ký mù đầy đủ."""
    e, n = key_manager.rsa_public_numbers
    h = 9876543210123456789
    m_star, r = simulate_client_blinding(h, e, n)

    assert 1 < r < n
    assert math.gcd(r, n) == 1

    s_star = BlindSignatureEngine.blind_sign(m_star)
    s = simulate_client_unblinding(s_star, r, n)

    assert BlindSignatureEngine.verify(h, s) is True
    assert BlindSignatureEngine.verify(h + 1, s) is False


def test_sanitizer_rgb_and_rgba_branches() -> None:
    """WB-CRYPTO-05: Kiểm thử cả 2 nhánh mode ảnh ('RGB' và 'RGBA') trong strip_image_metadata."""
    # Nhánh 1: Ảnh RGB có nhúng EXIF GPS
    rgb_img = Image.new("RGB", (32, 32), color=(120, 45, 200))
    exif_bytes = piexif.dump({
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: "N",
            piexif.GPSIFD.GPSLatitude: ((21, 1), (1, 1), (0, 1)),
        }
    })
    buf_rgb = io.BytesIO()
    rgb_img.save(buf_rgb, format="JPEG", exif=exif_bytes)

    cleaned_rgb = strip_image_metadata(buf_rgb.getvalue(), image_format="JPEG")
    with Image.open(io.BytesIO(cleaned_rgb)) as check_img:
        assert check_img.mode == "RGB"
        assert check_img._getexif() is None

    # Nhánh 2: Ảnh RGBA (PNG) chuyển đổi sang RGB khi xuất JPEG
    rgba_img = Image.new("RGBA", (32, 32), color=(10, 200, 100, 128))
    buf_rgba = io.BytesIO()
    rgba_img.save(buf_rgba, format="PNG")

    cleaned_from_rgba = strip_image_metadata(buf_rgba.getvalue(), image_format="JPEG")
    with Image.open(io.BytesIO(cleaned_from_rgba)) as check_rgba:
        assert check_rgba.mode == "RGB"
        assert check_rgba._getexif() is None

