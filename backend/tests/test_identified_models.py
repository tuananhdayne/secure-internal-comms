import pytest
from sqlalchemy import inspect
from app.db.session import engine, SessionLocal, Base
from app.models.identified import User, BlindSignQuota, Post, Comment


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_blind_sign_quota_has_no_timestamp_columns():
    """Bảo đảm nguyên tắc Unlinkability: Bảng blind_sign_quotas không có bất kỳ cột thời gian nào."""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("blind_sign_quotas")]
    
    # Không được chứa timestamp, requested_at, created_at, updated_at
    for col in columns:
        col_lower = col.lower()
        assert "time" not in col_lower, f"Phát hiện cột thời gian vi phạm Unlinkability: {col}"
        assert "date" not in col_lower, f"Phát hiện cột ngày vi phạm Unlinkability: {col}"
        assert "at" not in col_lower, f"Phát hiện cột mốc thời gian vi phạm Unlinkability: {col}"


def test_user_and_quota_creation():
    db = SessionLocal()
    try:
        user = User(
            employee_code="NV_TEST_01",
            password_hash="fakehash123",
            full_name="Nguyễn Văn Test",
            department="An Toàn Thông Tin",
            role="EMPLOYEE"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.is_active is True

        quota = BlindSignQuota(
            user_id=user.id,
            week_epoch=202644,
            request_count=1
        )
        db.add(quota)
        db.commit()
        db.refresh(quota)

        assert quota.id is not None
        assert quota.request_count == 1
    finally:
        db.close()


def test_post_and_comment_creation():
    db = SessionLocal()
    try:
        user = User(
            employee_code="AD_TEST_01",
            password_hash="fakehash123",
            full_name="Admin Test",
            department="IT",
            role="SYSTEM_ADMIN"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        post = Post(
            author_id=user.id,
            title="Quy định mới về ATTT",
            content="Toàn thể nhân viên tuân thủ chính sách...",
            category="ANNOUNCEMENT",
            is_pinned=True
        )
        db.add(post)
        db.commit()
        db.refresh(post)

        comment = Comment(
            post_id=post.id,
            author_id=user.id,
            content="Đã ghi nhận thông báo."
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)

        assert post.id is not None
        assert comment.id is not None
        assert comment.post_id == post.id
    finally:
        db.close()
