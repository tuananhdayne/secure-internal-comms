"""Cô lập môi trường kiểm thử.

Trước đây bộ test ghi thẳng vào `backend/app.db` và `backend/uploads/` thật: các test web
đặt lại mật khẩu của AD001/TT001 nên tài khoản demo (admin123/officer123) bị hỏng sau mỗi
lần chạy pytest, và thư mục uploads đầy tệp rác. File này trỏ CSDL + uploads sang thư mục
tạm TRƯỚC khi `app` được import (Settings và engine được khởi tạo lúc import).
"""
import os

import pytest
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="atbm_test_"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}")
os.environ.setdefault("UPLOAD_DIR", str(_TMP / "uploads"))
os.environ.setdefault("ENABLE_API_DOCS", "true")  # test_main kiểm tra lược đồ OpenAPI

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.db import seed  # noqa: E402

Base.metadata.create_all(bind=engine)
with SessionLocal() as _db:
    seed.seed_database(_db)


@pytest.fixture(autouse=True)
def _reset_login_throttle():
    """Bộ đếm đăng nhập sai sống trong bộ nhớ tiến trình: reset để các test không ảnh hưởng nhau."""
    from app.services.login_throttle import login_throttle
    login_throttle.reset()
    yield
    login_throttle.reset()
