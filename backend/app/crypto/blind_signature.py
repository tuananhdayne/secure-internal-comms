import hashlib
import math
from typing import List, Tuple
from app.crypto.key_manager import key_manager


class BlindSignatureEngine:
    """Thực thi thuật toán Chữ ký mù RSA của David Chaum (RSA Blind Signature).

    Bảo đảm toán học:
    - Tính toàn vẹn: s^e mod N == H
    - Tính không thể liên kết (Unlinkability): Server chỉ thấy m* = (H * r^e) mod N,
      hoàn toàn không thể suy ra chữ ký s = (s* * r^-1) mod N thuộc về nhân viên nào.
    """

    @staticmethod
    def compute_payload_hash(
        category: str,
        encrypted_title: str,
        encrypted_description: str,
        case_token: str,
        case_public_key: str,
        evidence_file_hashes: List[str]
    ) -> int:
        """Tính mã băm H ràng buộc toàn vẹn cả nội dung đã mã hóa và danh sách file bằng chứng.

        H = SHA256(Category || EncTitle || EncDesc || Case_Token || Case_PubKey || Hash(File_1) || ... || Hash(File_k)) mod N
        """
        hasher = hashlib.sha256()
        hasher.update(category.encode("utf-8"))
        hasher.update(b"|")
        hasher.update(encrypted_title.encode("utf-8"))
        hasher.update(b"|")
        hasher.update(encrypted_description.encode("utf-8"))
        hasher.update(b"|")
        hasher.update(case_token.encode("utf-8"))
        hasher.update(b"|")
        hasher.update(case_public_key.encode("utf-8"))

        for file_hash in sorted(evidence_file_hashes):
            hasher.update(b"|")
            hasher.update(file_hash.encode("utf-8"))

        digest_bytes = hasher.digest()
        h_int = int.from_bytes(digest_bytes, byteorder="big")

        _, n = key_manager.rsa_public_numbers
        return h_int % n

    @staticmethod
    def blind_sign(m_star: int) -> int:
        """Server Ban Thanh tra thực hiện ký mù s* = (m*)^d mod N."""
        d, n = key_manager.rsa_private_numbers
        if m_star <= 1 or m_star >= n:
            raise ValueError("Giá trị làm mù m* không hợp lệ (ngoài khoảng 1 < m* < N).")

        # s* = (m*)^d mod N
        s_star = pow(m_star, d, n)
        return s_star

    @staticmethod
    def verify(h: int, s: int) -> bool:
        """Xác minh tính hợp lệ toán học của chữ ký sau khi bóc mù:
        s^e mod N == H
        """
        e, n = key_manager.rsa_public_numbers
        if s <= 1 or s >= n:
            return False

        recovered_h = pow(s, e, n)
        return recovered_h == h


# Helper Client-side for tests / simulation
def simulate_client_blinding(h: int, e: int, n: int) -> Tuple[int, int]:
    """Client chọn ngẫu nhiên r và tính m* = (H * r^e) mod N."""
    import secrets
    while True:
        # Sinh số ngẫu nhiên r 1024-bit
        r = secrets.randbelow(n - 2) + 2
        if math.gcd(r, n) == 1:
            break

    # m* = (h * (r^e mod n)) mod n
    r_pow_e = pow(r, e, n)
    m_star = (h * r_pow_e) % n
    return m_star, r


def simulate_client_unblinding(s_star: int, r: int, n: int) -> int:
    """Client bóc mù s = (s* * r^-1) mod N."""
    r_inv = pow(r, -1, n)
    s = (s_star * r_inv) % n
    return s
