import pytest
from sqlalchemy import text
from app.db.session import engine, SessionLocal, Base


def test_db_session_connection():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT 1")).scalar()
        assert result == 1
    finally:
        db.close()


def test_sqlite_foreign_keys_enabled():
    db = SessionLocal()
    try:
        fk_status = db.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk_status == 1
    finally:
        db.close()


def test_base_declarative():
    assert hasattr(Base, "metadata")
