import os
from typing import Dict, Tuple
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HKDF_INFO = b"atbm-ecies-aes256gcm"


def aes_gcm_encrypt(key: bytes, plaintext: bytes) -> Tuple[bytes, bytes, bytes]:
    """Mã hóa đối xứng AES-256-GCM.
    
    Args:
        key: Khóa AES 32 bytes (256-bit).
        plaintext: Dữ liệu cần mã hóa.
        
    Returns:
        Tuple (iv: 12 bytes, ciphertext: bytes, auth_tag: 16 bytes).
    """
    if len(key) != 32:
        raise ValueError("Khóa AES-256 yêu cầu đúng 32 bytes.")

    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    # Trong cryptography, aesgcm.encrypt trả về ciphertext + 16-byte tag ở đuôi
    encrypted_blob = aesgcm.encrypt(iv, plaintext, None)
    ciphertext = encrypted_blob[:-16]
    tag = encrypted_blob[-16:]
    return iv, ciphertext, tag


def aes_gcm_decrypt(key: bytes, iv: bytes, ciphertext: bytes, tag: bytes) -> bytes:
    """Giải mã đối xứng AES-256-GCM kèm kiểm tra tính toàn vẹn (auth_tag).
    
    Args:
        key: Khóa AES 32 bytes.
        iv: Vector khởi tạo 12 bytes.
        ciphertext: Bản mã.
        tag: Thẻ xác thực 16 bytes.
        
    Returns:
        Bản rõ sau khi giải mã thành công.
        
    Raises:
        cryptography.exceptions.InvalidTag: Nếu dữ liệu bị can thiệp hoặc sai khóa/tag.
    """
    aesgcm = AESGCM(key)
    full_encrypted_blob = ciphertext + tag
    return aesgcm.decrypt(iv, full_encrypted_blob, None)


def ecies_encrypt(recipient_pub_hex: str, plaintext: bytes) -> Dict[str, str]:
    """Mã hóa bất đối xứng lai ECIES (ECDH P-256 + HKDF-SHA256 + AES-256-GCM).
    
    Dùng để bảo vệ tiêu đề, nội dung, khóa file bằng chứng của hồ sơ tố giác 
    và các tin nhắn chat E2EE.
    
    Args:
        recipient_pub_hex: Khóa công khai EC của người nhận (65 bytes uncompressed, dạng hex).
        plaintext: Dữ liệu cần mã hóa dạng bytes.
        
    Returns:
        Dict chứa các giá trị hex:
        - ephemeral_public_key: Khóa công khai tạm thời của bên gửi (130 ký tự hex).
        - iv: Vector khởi tạo (24 ký tự hex).
        - ciphertext: Bản mã (chuỗi hex).
        - auth_tag: Thẻ xác thực tính toàn vẹn (32 ký tự hex).
    """
    # 1. Parse khóa công khai người nhận
    recipient_pub_bytes = bytes.fromhex(recipient_pub_hex)
    recipient_pub = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(),
        recipient_pub_bytes
    )

    # 2. Sinh cặp khóa tạm thời (Ephemeral KeyPair)
    ephemeral_priv = ec.generate_private_key(ec.SECP256R1())
    ephemeral_pub = ephemeral_priv.public_key()
    ephemeral_pub_bytes = ephemeral_pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )

    # 3. Tính toán Shared Secret qua ECDH
    shared_secret = ephemeral_priv.exchange(ec.ECDH(), recipient_pub)

    # 4. Dẫn xuất khóa AES-256 qua HKDF-SHA256
    derived_aes_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=HKDF_INFO
    ).derive(shared_secret)

    # 5. Mã hóa bằng AES-256-GCM
    iv, ciphertext, tag = aes_gcm_encrypt(derived_aes_key, plaintext)

    return {
        "ephemeral_public_key": ephemeral_pub_bytes.hex(),
        "iv": iv.hex(),
        "ciphertext": ciphertext.hex(),
        "auth_tag": tag.hex()
    }


def ecies_decrypt(
    recipient_priv_key: ec.EllipticCurvePrivateKey,
    ephemeral_pub_hex: str,
    iv_hex: str,
    ciphertext_hex: str,
    tag_hex: str
) -> bytes:
    """Giải mã gói tin ECIES bằng Khóa riêng EC của người nhận.
    
    Args:
        recipient_priv_key: Khóa riêng ECC P-256 của người nhận.
        ephemeral_pub_hex: Khóa công khai tạm thời dạng hex.
        iv_hex: Vector khởi tạo dạng hex.
        ciphertext_hex: Bản mã dạng hex.
        tag_hex: Thẻ xác thực dạng hex.
        
    Returns:
        Bản rõ gốc dạng bytes.
    """
    # 1. Parse khóa công khai tạm thời
    ephemeral_pub_bytes = bytes.fromhex(ephemeral_pub_hex)
    ephemeral_pub = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(),
        ephemeral_pub_bytes
    )

    # 2. Tính Shared Secret qua ECDH
    shared_secret = recipient_priv_key.exchange(ec.ECDH(), ephemeral_pub)

    # 3. Dẫn xuất khóa AES-256 tương ứng
    derived_aes_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=HKDF_INFO
    ).derive(shared_secret)

    # 4. Giải mã AES-256-GCM
    return aes_gcm_decrypt(
        key=derived_aes_key,
        iv=bytes.fromhex(iv_hex),
        ciphertext=bytes.fromhex(ciphertext_hex),
        tag=bytes.fromhex(tag_hex)
    )
