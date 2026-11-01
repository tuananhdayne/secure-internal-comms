from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    """Cụm 1: Quản lý người dùng và định danh nhân viên doanh nghiệp."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="EMPLOYEE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    quotas: Mapped[List["BlindSignQuota"]] = relationship("BlindSignQuota", back_populates="user", cascade="all, delete-orphan")
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="author")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="author", cascade="all, delete-orphan")


class BlindSignQuota(Base):
    """Cụm 1: Hạn mức xin chữ ký mù tuần của nhân viên.
    
    NGUYÊN TẮC AN TOÀN BẢO MẬT TUYỆT ĐỐI (UNLINKABILITY):
    Bảng này NGHIÊM CẤM có bất kỳ cột timestamp (created_at, updated_at, last_requested_at)
    nào để loại trừ hoàn toàn nguy cơ Correlation Attack so khớp thời gian với hồ sơ tố giác.
    """
    __tablename__ = "blind_sign_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_epoch: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # Định dạng YYYYWW, vd: 202644
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "week_epoch", name="uq_user_week_quota"),
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="quotas")


class Post(Base):
    """Cụm 1: Bài viết truyền thông nội bộ, thông báo doanh nghiệp."""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="GENERAL", nullable=False, index=True)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    author: Mapped[Optional["User"]] = relationship("User", back_populates="posts")
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    """Cụm 1: Bình luận và trao đổi trên bản tin nội bộ."""
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    author: Mapped["User"] = relationship("User", back_populates="comments")
