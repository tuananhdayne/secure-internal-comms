import pytest
from app.db.session import engine, SessionLocal, Base
from app.models.identified import User, Post
from app.db.seed import seed_database


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_seed_database_creates_users_and_posts():
    db = SessionLocal()
    try:
        seed_database(db)

        # Kiểm tra 5 user cốt lõi
        codes = ["NV001", "NV002", "TT001", "GD001", "AD001"]
        for code in codes:
            user = db.query(User).filter(User.employee_code == code).first()
            assert user is not None, f"Thiếu user {code}"
            assert user.is_active is True

        # Kiểm tra bài viết
        posts = db.query(Post).all()
        assert len(posts) >= 3

        # Kiểm tra tính Idempotent (chạy lần 2 không văng lỗi)
        seed_database(db)
        users_count = db.query(User).count()
        assert users_count == 5
    finally:
        db.close()
