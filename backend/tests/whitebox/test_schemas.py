import pytest
from pydantic import ValidationError
from datetime import datetime, timezone

from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.schemas.posts import PostCreate, PostResponse, CommentCreate
from app.schemas.compliance import BlindSignRequest, OfficerKeysResponse
from app.schemas.anonymous import CaseCreateRequest, CaseStatusResponse, MessageCreateRequest
from app.schemas.officer import CaseStatusUpdate, OfficerReplyRequest


def test_auth_schemas():
    login = LoginRequest(employee_code="NV001", password="secure_password")
    assert login.employee_code == "NV001"

    token = TokenResponse(access_token="xyz.abc.jwt")
    assert token.token_type == "bearer"

    user = UserResponse(
        id=1,
        employee_code="NV001",
        full_name="Nguyễn Văn An",
        department="R&D",
        role="EMPLOYEE",
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    assert user.id == 1


def test_posts_schemas():
    post_in = PostCreate(title="Thong bao", content="Noi dung", category="ANNOUNCEMENT", is_pinned=True)
    assert post_in.is_pinned is True

    comment_in = CommentCreate(content="Binh luan hay")
    assert comment_in.content == "Binh luan hay"


def test_compliance_schemas():
    keys = OfficerKeysResponse(
        blind_sign_pub={"e": "10001", "n": "abcdef"},
        chat_pub_hex="04" + "a" * 128
    )
    assert keys.blind_sign_pub["e"] == "10001"

    req = BlindSignRequest(blinded_hash="1234567890abcdef")
    assert req.blinded_hash == "1234567890abcdef"


def test_anonymous_schemas():
    case_req = CaseCreateRequest(
        category="TAI_CHINH",
        encrypted_title="enc_title_hex",
        encrypted_description="enc_desc_hex",
        payload_ephemeral_pub="04" + "a" * 128,
        payload_iv="iv_hex",
        payload_auth_tag="tag_hex",
        case_token="uuid-token-1234",
        case_public_key="04" + "b" * 128,
        unblinded_signature="sig_hex"
    )
    assert case_req.case_token == "uuid-token-1234"

    msg_req = MessageCreateRequest(
        ephemeral_pub_key="04" + "c" * 128,
        nonce_iv="iv_hex",
        encrypted_message="msg_hex",
        auth_tag="tag_hex",
        digital_signature="sig_hex"
    )
    assert msg_req.nonce_iv == "iv_hex"
