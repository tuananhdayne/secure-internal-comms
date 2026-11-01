import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidTag

from app.crypto.ecies import ecies_encrypt, ecies_decrypt, aes_gcm_encrypt, aes_gcm_decrypt
from app.crypto.key_manager import key_manager


def test_aes_gcm_roundtrip():
    import secrets
    key = secrets.token_bytes(32)
    plaintext = b"Bao cao tuyet mat: Phat hien sai pham tai phong ke toan."

    iv, ciphertext, tag = aes_gcm_encrypt(key, plaintext)
    assert len(iv) == 12
    assert len(tag) == 16
    assert ciphertext != plaintext

    decrypted = aes_gcm_decrypt(key, iv, ciphertext, tag)
    assert decrypted == plaintext


def test_aes_gcm_tampered_tag():
    import secrets
    key = secrets.token_bytes(32)
    plaintext = b"Du lieu goc"

    iv, ciphertext, tag = aes_gcm_encrypt(key, plaintext)
    # Sửa 1 byte trong ciphertext
    tampered_ciphertext = bytearray(ciphertext)
    tampered_ciphertext[0] ^= 0xFF

    with pytest.raises(Exception):
        aes_gcm_decrypt(key, iv, bytes(tampered_ciphertext), tag)


def test_ecies_roundtrip_with_officer_key():
    officer_pub_hex = key_manager.ec_public_key_hex
    officer_priv_key = key_manager.ec_private_key

    plaintext = "Nội dung tố giác sai phạm rất quan trọng và nhạy cảm!".encode("utf-8")

    payload = ecies_encrypt(officer_pub_hex, plaintext)

    assert "ephemeral_public_key" in payload
    assert "iv" in payload
    assert "ciphertext" in payload
    assert "auth_tag" in payload
    assert len(payload["ephemeral_public_key"]) == 130  # 65 bytes * 2
    assert len(payload["iv"]) == 24  # 12 bytes * 2
    assert len(payload["auth_tag"]) == 32  # 16 bytes * 2

    decrypted = ecies_decrypt(
        officer_priv_key,
        payload["ephemeral_public_key"],
        payload["iv"],
        payload["ciphertext"],
        payload["auth_tag"]
    )
    assert decrypted == plaintext


def test_ecies_decrypt_with_wrong_key():
    officer_pub_hex = key_manager.ec_public_key_hex
    plaintext = b"Secret data"
    payload = ecies_encrypt(officer_pub_hex, plaintext)

    # Sinh khóa khác của attacker
    attacker_priv = ec.generate_private_key(ec.SECP256R1())

    with pytest.raises(Exception):
        ecies_decrypt(
            attacker_priv,
            payload["ephemeral_public_key"],
            payload["iv"],
            payload["ciphertext"],
            payload["auth_tag"]
        )
