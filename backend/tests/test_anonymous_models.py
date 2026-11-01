import pytest
from datetime import datetime, timezone
from sqlalchemy import inspect
from app.db.session import engine, SessionLocal, Base
from app.models.anonymous import WhistleCase, CaseEvidence, CaseMessage


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)


def test_anonymous_cluster_strict_zero_knowledge_invariants():
    """Bảo đảm nguyên tắc Cụm 2 Ẩn danh tuyệt đối:
    1. Không có bất kỳ cột nào chứa 'user', 'employee', 'ip', 'agent'.
    2. Không có bất kỳ Foreign Key nào tham chiếu sang Cụm 1.
    """
    inspector = inspect(engine)
    anonymous_tables = ["whistle_cases", "case_evidences", "case_messages"]

    forbidden_exact = ["user_id", "employee_id", "employee_code", "ip_address", "ip", "user_agent", "session_id"]

    for table_name in anonymous_tables:
        columns = [col["name"].lower() for col in inspector.get_columns(table_name)]
        for col in columns:
            assert col not in forbidden_exact, f"Vi phạm nguyên tắc ẩn danh! Cột '{col}' trong bảng '{table_name}' chứa thông tin định danh."
            assert not col.startswith("user_"), f"Cột '{col}' trỏ đến user"
            assert not col.startswith("employee_"), f"Cột '{col}' trỏ đến employee"
            assert not col.startswith("ip_"), f"Cột '{col}' trỏ đến ip"

        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            referred_table = fk["referred_table"]
            assert referred_table in anonymous_tables, f"Vi phạm cách ly Cụm! Bảng '{table_name}' có FK trỏ sang '{referred_table}' của Cụm 1."


def test_whistle_case_and_evidence_creation():
    db = SessionLocal()
    try:
        # Giờ bucket được làm tròn giờ chẵn
        now = datetime.now(timezone.utc)
        hour_bucket = now.replace(minute=0, second=0, microsecond=0)

        case = WhistleCase(
            case_token="case-uuid-1234-5678-abcd",
            category="TAI_CHINH",
            encrypted_title="0123456789abcdef",
            encrypted_description="fedcba9876543210",
            payload_ephemeral_pub="04" + "a" * 128,
            payload_iv="b" * 24,
            payload_auth_tag="c" * 32,
            unblinded_signature="1234567890abcdef",
            case_public_key="04" + "d" * 128,
            status="PENDING",
            created_bucket=hour_bucket
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        assert case.id is not None
        assert case.created_bucket.minute == 0
        assert case.created_bucket.second == 0

        # Thêm file bằng chứng mã hóa
        evidence = CaseEvidence(
            case_id=case.id,
            file_url="./uploads/evidences/enc_file_1.bin",
            file_sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            mime_type="application/octet-stream"
        )
        db.add(evidence)

        # Thêm tin nhắn E2EE chat
        message = CaseMessage(
            case_id=case.id,
            sender_type="ANONYMOUS_WHISTLEBLOWER",
            ephemeral_pub_key="04" + "e" * 128,
            nonce_iv="f" * 24,
            encrypted_message="a1b2c3d4",
            auth_tag="e5f6a7b8" * 4,
            digital_signature="signature_hex"
        )
        db.add(message)
        db.commit()

        assert evidence.id is not None
        assert message.id is not None
        assert len(case.evidences) == 1
        assert len(case.messages) == 1
    finally:
        db.close()
