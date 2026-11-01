from datetime import datetime, timezone
from typing import List
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class WhistleCase(Base):
    """Cụm 2: Hồ sơ Tố giác Sai phạm Ẩn danh (Zero-Knowledge).
    
    RÀNG BUỘC TOÀN VẸN VÀ BẢO MẬT:
    1. Tuyệt đối không có bất kỳ trường định danh nào (user_id, employee_code, ip_address).
    2. Cột `created_bucket` lưu thời gian làm tròn tới giờ (hour bucket) để bảo vệ người tố
       giác trước đòn tấn công tương quan thời gian (Timing Correlation Attack).
    3. `encrypted_title` và `encrypted_description` đã được mã hóa bằng ECIES (khóa công khai
       của Ban Thanh tra). Server Admin / DBA không thể đọc được nội dung.
    """
    __tablename__ = "whistle_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    encrypted_title: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_description: Mapped[str] = mapped_column(Text, nullable=False)
    payload_ephemeral_pub: Mapped[str] = mapped_column(String(130), nullable=False)
    payload_iv: Mapped[str] = mapped_column(String(24), nullable=False)
    payload_auth_tag: Mapped[str] = mapped_column(String(32), nullable=False)
    unblinded_signature: Mapped[str] = mapped_column(Text, nullable=False)
    case_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    created_bucket: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Relationships trong nội bộ Cụm 2
    evidences: Mapped[List["CaseEvidence"]] = relationship("CaseEvidence", back_populates="case", cascade="all, delete-orphan")
    messages: Mapped[List["CaseMessage"]] = relationship("CaseMessage", back_populates="case", cascade="all, delete-orphan")


class CaseEvidence(Base):
    """Cụm 2: Tệp bằng chứng đính kèm (Hình ảnh, Âm thanh, PDF).
    
    Tất cả các tệp lưu trữ trên server đều ở dạng ĐÃ ĐƯỢC MÃ HÓA (AES-256-GCM qua File_Key).
    Mã băm SHA-256 của file được đưa vào công thức băm H khi xin chữ ký mù, chống tráo đổi file.
    """
    __tablename__ = "case_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("whistle_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), default="application/octet-stream", nullable=False)

    # Relationship
    case: Mapped["WhistleCase"] = relationship("WhistleCase", back_populates="evidences")


class CaseMessage(Base):
    """Cụm 2: Kênh trao đổi 2 chiều mã hóa đầu-cuối (E2EE Chat) giữa Người tố giác và Thanh tra."""
    __tablename__ = "case_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(Integer, ForeignKey("whistle_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ANONYMOUS_WHISTLEBLOWER hoặc COMPLIANCE_OFFICER
    ephemeral_pub_key: Mapped[str] = mapped_column(String(130), nullable=False)
    nonce_iv: Mapped[str] = mapped_column(String(24), nullable=False)
    encrypted_message: Mapped[str] = mapped_column(Text, nullable=False)
    auth_tag: Mapped[str] = mapped_column(String(32), nullable=False)
    digital_signature: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    case: Mapped["WhistleCase"] = relationship("WhistleCase", back_populates="messages")
