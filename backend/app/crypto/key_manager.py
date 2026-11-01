import os
from pathlib import Path
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization

from app.core.config import settings


class KeyManager:
    """Quản lý 2 cặp khóa độc lập của Ban Thanh tra (Key Separation):
    1. RSA-2048: Chỉ dùng ký mù (Blind Signing).
    2. ECC P-256: Dùng mã hóa E2EE và ký xác thực Chat 2 chiều.
    """

    def __init__(self, keys_dir: Path | None = None) -> None:
        self.keys_dir = keys_dir or settings.keys_path
        self.rsa_key_path = self.keys_dir / "officer_blind_rsa.pem"
        self.ec_key_path = self.keys_dir / "officer_chat_ec.pem"
        self._rsa_private_key: rsa.RSAPrivateKey | None = None
        self._ec_private_key: ec.EllipticCurvePrivateKey | None = None
        self._load_or_generate_keys()

    def _load_or_generate_keys(self) -> None:
        # 1. RSA-2048 Key for Blind Signatures
        if self.rsa_key_path.exists():
            with open(self.rsa_key_path, "rb") as f:
                self._rsa_private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )  # type: ignore[assignment]
        else:
            self._rsa_private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            pem = self._rsa_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(self.rsa_key_path, "wb") as f:
                f.write(pem)

        # 2. ECC P-256 Key for E2EE Chat & Report Encryption
        if self.ec_key_path.exists():
            with open(self.ec_key_path, "rb") as f:
                self._ec_private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )  # type: ignore[assignment]
        else:
            self._ec_private_key = ec.generate_private_key(
                ec.SECP256R1()
            )
            pem = self._ec_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(self.ec_key_path, "wb") as f:
                f.write(pem)

    # --- RSA Blind Signatures ---
    @property
    def rsa_public_numbers(self) -> Tuple[int, int]:
        """Trả về cặp (e, n) của RSA Blind Sign."""
        assert self._rsa_private_key is not None
        pub = self._rsa_private_key.public_key().public_numbers()
        return pub.e, pub.n

    @property
    def rsa_private_numbers(self) -> Tuple[int, int]:
        """Trả về cặp (d, n) của RSA Blind Sign."""
        assert self._rsa_private_key is not None
        priv = self._rsa_private_key.private_numbers()
        return priv.d, priv.public_numbers.n

    # --- ECC E2EE Chat ---
    @property
    def ec_private_key(self) -> ec.EllipticCurvePrivateKey:
        assert self._ec_private_key is not None
        return self._ec_private_key

    @property
    def ec_public_key_hex(self) -> str:
        """Trả về khóa công khai EC uncompressed dạng hex (65 bytes = 130 hex chars)."""
        assert self._ec_private_key is not None
        pub = self._ec_private_key.public_key()
        raw_bytes = pub.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        return raw_bytes.hex()


key_manager = KeyManager()
