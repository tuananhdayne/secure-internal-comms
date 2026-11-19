"""Hằng số nghiệp vụ dùng chung toàn hệ thống.

Trước đây các chuỗi vai trò / trạng thái được gõ tay rải rác trong từng route và hai nơi
(API `/officer` và Web `/admin/cases`) dùng hai tập trạng thái khác nhau. Mọi chỗ cần so sánh
vai trò hay kiểm tra trạng thái hợp lệ nên import từ đây.

Giá trị vẫn là chuỗi thường (không phải Enum) để khớp cột String trong CSDL hiện có.
"""
from typing import FrozenSet


class Role:
    EMPLOYEE = "EMPLOYEE"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    BOARD_DIRECTOR = "BOARD_DIRECTOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"

    ALL: FrozenSet[str] = frozenset({EMPLOYEE, COMPLIANCE_OFFICER, BOARD_DIRECTOR, SYSTEM_ADMIN})
    # Quyền của từng vai trò: xem app/core/permissions.py (bảng phân quyền duy nhất).


class CaseStatus:
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    INVESTIGATING = "INVESTIGATING"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"  # bí danh cũ của INVESTIGATING
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"

    ALL: FrozenSet[str] = frozenset({PENDING, RECEIVED, INVESTIGATING, UNDER_INVESTIGATION, RESOLVED, REJECTED})


class SenderType:
    WHISTLEBLOWER = "ANONYMOUS_WHISTLEBLOWER"
    OFFICER = "COMPLIANCE_OFFICER"


# Tiền tố trong cột `digital_signature` của tin nhắn do Thanh tra gửi qua Web:
# "ENC:<eph_pub>:<iv>:<ciphertext>:<tag>" = bản sao mã hóa cho chính Ban Thanh tra.
OFFICER_COPY_PREFIX = "ENC:"
# Bản ghi cũ (trước khi vá) lưu bản rõ sau tiền tố này.
LEGACY_OFFICER_NOTE_PREFIX = "OFFICER_NOTE:"

# Dấu phân cách tiêu đề / nội dung bên trong bản rõ ECIES của hồ sơ.
TITLE_DESC_SEPARATOR = "|||"
