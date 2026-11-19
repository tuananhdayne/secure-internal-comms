"""Kiểm thử giao thức bằng bộ dữ liệu DÙNG CHUNG với app Android (protocol/test_vectors.json).

File Kotlin tương ứng: android/app/src/test/java/com/atbm/app/domain/crypto/CryptoUnitTest.kt.
Nếu sửa thông điệp ký mù / PSS / ECIES / chữ ký ở một bên, cả hai test phải cùng đạt.
"""
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.crypto.blind_signature import BlindSignatureEngine, client_blind, client_finalize, emsa_pss_encode, payload_message
from app.crypto.ecies import ecies_decrypt

VECTORS = json.loads((Path(__file__).resolve().parents[3] / "protocol" / "test_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", VECTORS["payload_message"]["cases"], ids=lambda c: c["name"])
def test_payload_message_matches_vector(case):
    msg = payload_message(case["category"], case["encrypted_title"], case["encrypted_description"],
                          case["case_token"], case["case_public_key"], case["evidence_file_hashes"])
    assert msg.hex() == case["expected_message_hex"]


def test_rfc9474_blind_signature_vector():
    v = VECTORS["blind_signature"]
    n, e = int(v["n_hex"], 16), int(v["e_hex"], 16)
    msg, salt = bytes.fromhex(v["message_hex"]), bytes.fromhex(v["salt_hex"])
    assert emsa_pss_encode(msg, n.bit_length() - 1, salt).hex() == v["encoded_message_hex"]
    blinded, r, m = client_blind(msg, e, n, salt=salt, r=int(v["r_hex"], 16))
    assert format(blinded, "x") == v["blinded_hex"]
    s = client_finalize(int(v["blind_signature_hex"], 16), r, m, e, n)
    assert format(s, "x") == v["signature_hex"]
    # Chữ ký cuối cùng là RSASSA-PSS chuẩn: thư viện `cryptography` xác minh được
    assert BlindSignatureEngine.verify(msg, s, e, n)
    assert not BlindSignatureEngine.verify(msg + b"x", s, e, n)


@pytest.mark.parametrize("idx", range(len(VECTORS["ecies"]["cases"])))
def test_ecies_vector_decrypts(idx):
    ev = VECTORS["ecies"]
    priv = serialization.load_der_private_key(bytes.fromhex(ev["recipient_private_pkcs8_hex"]), password=None)
    c = ev["cases"][idx]
    plain = ecies_decrypt(priv, c["ephemeral_public_key"], c["iv"], c["ciphertext"], c["auth_tag"])
    assert plain.decode("utf-8") == c["plaintext_utf8"]


def test_ecdsa_vector_verifies():
    v = VECTORS["ecdsa"]
    pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), bytes.fromhex(v["public_hex"]))
    pub.verify(bytes.fromhex(v["signature_der_hex"]), v["message_utf8"].encode("utf-8"), ec.ECDSA(hashes.SHA256()))
