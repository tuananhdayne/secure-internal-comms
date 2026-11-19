"""Kiểm thử giao thức bằng bộ dữ liệu DÙNG CHUNG với app Android (protocol/test_vectors.json).

File Kotlin tương ứng: android/app/src/test/java/com/atbm/app/domain/crypto/CryptoUnitTest.kt.
Nếu sửa cách tính H / ECIES / chữ ký ở một bên, cả hai test phải cùng đạt.
"""
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.crypto.blind_signature import BlindSignatureEngine
from app.crypto.ecies import ecies_decrypt

VECTORS = json.loads((Path(__file__).resolve().parents[3] / "protocol" / "test_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", VECTORS["payload_hash"]["cases"], ids=lambda c: c["name"])
def test_payload_hash_matches_vector(case):
    n = int(VECTORS["payload_hash"]["rsa_n_hex"], 16)
    h = BlindSignatureEngine.compute_payload_hash(
        case["category"], case["encrypted_title"], case["encrypted_description"],
        case["case_token"], case["case_public_key"], case["evidence_file_hashes"], n=n)
    assert format(h, "x") == case["expected_h_hex"]


def test_blind_signature_math_matches_vector():
    v = {k: int(x, 16) for k, x in VECTORS["blind_signature"].items()}
    n, e = v["n_hex"], v["e_hex"]
    assert (v["h_hex"] * pow(v["r_hex"], e, n)) % n == v["m_star_hex"]
    assert (v["s_star_hex"] * pow(v["r_hex"], -1, n)) % n == v["s_hex"]
    assert pow(v["s_hex"], e, n) == v["h_hex"]


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
