"""Nghiệp vụ mật mã của hồ sơ tố giác (phía Ban Thanh tra).

- Giải mã bản rõ hồ sơ (ECIES bằng khóa riêng EC của Ban Thanh tra).
- Giải mã tin nhắn trong kênh E2EE để hiển thị cho Thanh tra.
- Mã hóa phản hồi của Thanh tra gửi tới người tố giác.
- Ẩn các trường nội bộ khi trả tin nhắn về cho client ẩn danh.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from app.core.constants import (
    LEGACY_OFFICER_NOTE_PREFIX,
    OFFICER_COPY_PREFIX,
    SenderType,
    TITLE_DESC_SEPARATOR,
)
from app.crypto.ecies import ecies_decrypt, ecies_encrypt
from app.crypto.key_manager import key_manager
from app.models.anonymous import CaseMessage, WhistleCase

logger = logging.getLogger(__name__)

DECRYPT_FAILED_TITLE = "Không đọc được nội dung hồ sơ"
DECRYPT_FAILED_DESC = "Nội dung hồ sơ này không thể hiển thị (có thể đã bị hỏng khi truyền hoặc được gửi bằng phiên bản ứng dụng cũ). Vui lòng liên hệ bộ phận kỹ thuật nếu cần hỗ trợ."
DEFAULT_TITLE = "Tiêu đề hồ sơ"


@dataclass(frozen=True)
class DecryptedCase:
    title: str
    description: str
    ok: bool
    error: str = ""


def decrypt_case_payload(case: WhistleCase) -> DecryptedCase:
    """Giải mã nội dung hồ sơ. Không ném lỗi: trả `ok=False` kèm thông điệp để route tự quyết định."""
    try:
        plaintext = ecies_decrypt(
            recipient_priv_key=key_manager.ec_private_key,
            ephemeral_pub_hex=case.payload_ephemeral_pub,
            iv_hex=case.payload_iv,
            ciphertext_hex=case.encrypted_description,
            tag_hex=case.payload_auth_tag,
        ).decode("utf-8")
    except Exception as exc:  # InvalidTag, ValueError (hex sai), UnicodeDecodeError...
        logger.warning("Không giải mã được hồ sơ id=%s: %s", case.id, type(exc).__name__)
        return DecryptedCase(DECRYPT_FAILED_TITLE, DECRYPT_FAILED_DESC, ok=False, error=str(exc))

    if TITLE_DESC_SEPARATOR in plaintext:
        title, description = plaintext.split(TITLE_DESC_SEPARATOR, 1)
    else:
        title, description = DEFAULT_TITLE, plaintext
    return DecryptedCase(title, description, ok=True)


def decrypt_message_for_officer(message: CaseMessage) -> str:
    """Trả về nội dung tin nhắn ở dạng đọc được cho Ban Thanh tra."""
    if message.sender_type == SenderType.OFFICER:
        sig = message.digital_signature or ""
        if sig.startswith(OFFICER_COPY_PREFIX):
            # Bản sao Thanh tra tự mã hóa cho mình: "ENC:<eph>:<iv>:<ct>:<tag>"
            try:
                _, eph, iv, ct, tag = sig.split(":", 4)
                return ecies_decrypt(key_manager.ec_private_key, eph, iv, ct, tag).decode("utf-8")
            except Exception as exc:
                logger.warning("Lỗi giải mã bản sao tin nhắn Officer id=%s: %s", message.id, type(exc).__name__)
                return "(Không thể hiển thị tin nhắn này)"
        if sig.startswith(LEGACY_OFFICER_NOTE_PREFIX):
            return sig[len(LEGACY_OFFICER_NOTE_PREFIX):]
        return "(Tin nhắn đã gửi tới người tố giác)"

    # Tin nhắn người tố giác: ECIES tới khóa công khai của Ban Thanh tra
    try:
        return ecies_decrypt(
            recipient_priv_key=key_manager.ec_private_key,
            ephemeral_pub_hex=message.ephemeral_pub_key,
            iv_hex=message.nonce_iv,
            ciphertext_hex=message.encrypted_message,
            tag_hex=message.auth_tag,
        ).decode("utf-8")
    except Exception as exc:
        logger.warning("Lỗi giải mã tin nhắn tố giác id=%s: %s", message.id, type(exc).__name__)
        return "(Không thể hiển thị tin nhắn này)"


def build_officer_reply(case: WhistleCase, text: str) -> CaseMessage:
    """Tạo bản ghi tin nhắn Thanh tra -> người tố giác (chưa add/commit).

    - Bản chính: ECIES tới `case.case_public_key` (chỉ người tố giác giải mã được).
    - Bản sao: ECIES tới khóa của Ban Thanh tra, lưu trong `digital_signature` với tiền tố
      `ENC:` để Thanh tra xem lại lịch sử mà CSDL không chứa bản rõ.
    """
    data = text.encode("utf-8")
    for_whistleblower = ecies_encrypt(case.case_public_key, data)
    for_officer = ecies_encrypt(key_manager.ec_public_key_hex, data)
    officer_copy = OFFICER_COPY_PREFIX + ":".join(
        (for_officer["ephemeral_public_key"], for_officer["iv"], for_officer["ciphertext"], for_officer["auth_tag"])
    )
    return CaseMessage(
        case_id=case.id,
        sender_type=SenderType.OFFICER,
        ephemeral_pub_key=for_whistleblower["ephemeral_public_key"],
        nonce_iv=for_whistleblower["iv"],
        encrypted_message=for_whistleblower["ciphertext"],
        auth_tag=for_whistleblower["auth_tag"],
        digital_signature=officer_copy,
    )


def masked_signature_for_anonymous(message: CaseMessage) -> str:
    """Không trả bản sao nội bộ của Thanh tra (ENC:/OFFICER_NOTE:) về cho client ẩn danh."""
    sig = message.digital_signature or ""
    if message.sender_type == SenderType.OFFICER and (
        sig.startswith(OFFICER_COPY_PREFIX) or sig.startswith(LEGACY_OFFICER_NOTE_PREFIX)
    ):
        return "OFFICER_P256_VERIFIED_SIGNATURE"
    return sig


def officer_message_view(message: CaseMessage) -> Dict[str, object]:
    """Dữ liệu tin nhắn đã giải mã cho modal Thanh tra (JSON)."""
    return {
        "id": message.id,
        "sender_type": message.sender_type,
        "content": decrypt_message_for_officer(message),
        "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }
