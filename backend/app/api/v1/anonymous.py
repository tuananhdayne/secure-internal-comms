"""Cụm 2 — REST API ẩn danh (không JWT): nộp hồ sơ, tra cứu trạng thái, chat E2EE.

NGUYÊN TẮC BẢO MẬT CỦA CẢ MODULE:
- Không đọc / ghi log IP, User-Agent hay bất kỳ định danh nào (xem `app/core/logging.py`:
  request ẩn danh không được ghi access log; header IP bị xóa trong middleware).
- `case_token` là "bí mật cầm tay" của người tố giác: không log, không đưa vào thông báo lỗi.

Luồng nộp hồ sơ (POST /cases):
    lưu tệp (services.evidence) -> tính H (BlindSignatureEngine.compute_payload_hash)
    -> kiểm s^e mod N == H -> lưu WhistleCase với created_bucket làm tròn giờ.
"""
import re
from datetime import datetime, timezone
from typing import List

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.core.constants import CaseStatus, SenderType
from app.crypto.blind_signature import BlindSignatureEngine, parse_rsa_int
from app.db.session import get_db
from app.models.anonymous import CaseEvidence, CaseMessage, WhistleCase
from app.schemas.anonymous import (
    CaseEvidenceResponse,
    CaseMessageResponse,
    CaseStatusResponse,
    CaseSubmitResponse,
    MessageCreateRequest,
)
from app.services import evidence as evidence_service
from app.services.case_crypto import masked_signature_for_anonymous

router = APIRouter(tags=["Anonymous Whistleblowing & E2EE Chat"])

ERR_TOKEN_EXISTS = "Mã định danh hồ sơ (case_token) đã tồn tại trong hệ thống."
ERR_SIG_FORMAT = "Định dạng chữ ký mù không hợp lệ."
ERR_SIG_INVALID = "Chữ ký mù không hợp lệ hoặc dữ liệu bằng chứng đã bị tráo đổi."
ERR_CASE_NOT_FOUND = "Không tìm thấy hồ sơ với mã case_token này."
ERR_OWNER_SIG = "Chữ ký số xác thực quyền chủ sở hữu hồ sơ không hợp lệ."
ERR_REPLAY = "Tin nhắn này đã được gửi trước đó (phát hiện gửi lại)."


def _hour_bucket(now: datetime) -> datetime:
    """Làm tròn xuống đầu giờ để chống tấn công tương quan thời gian."""
    return now.replace(minute=0, second=0, microsecond=0)


def _find_case(db: Session, case_token: str) -> WhistleCase:
    case = db.query(WhistleCase).filter(WhistleCase.case_token == case_token.strip()).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_CASE_NOT_FOUND)
    return case


_STRONG_TOKEN = re.compile(r"[A-Za-z0-9_-]{24,64}")
MIN_TOKEN_ALNUM = 24
ERR_WEAK_TOKEN = "Mã hồ sơ không hợp lệ. Vui lòng cập nhật ứng dụng lên phiên bản mới nhất."


@router.post("/cases", response_model=CaseSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_anonymous_case(
    category: str = Form(...),
    encrypted_title: str = Form(...),
    encrypted_description: str = Form(...),
    payload_ephemeral_pub: str = Form(...),
    payload_iv: str = Form(...),
    payload_auth_tag: str = Form(...),
    case_token: str = Form(...),
    case_public_key: str = Form(...),
    unblinded_signature: str = Form(...),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
) -> CaseSubmitResponse:
    """Nộp hồ sơ tố giác ẩn danh, xác minh bằng chữ ký mù RSA (s^e mod N == H)."""
    token = case_token.strip()
    # Mã hồ sơ là bí mật duy nhất để tra cứu ẩn danh -> bắt buộc đủ dài, chỉ ký tự an toàn
    # (app sinh "CASE-" + 32 hex ngẫu nhiên). Từ chối mã ngắn / đoán được (vd. CASE-<thời gian>).
    if not _STRONG_TOKEN.fullmatch(token) or sum(ch.isalnum() for ch in token) < MIN_TOKEN_ALNUM:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_WEAK_TOKEN)
    if db.query(WhistleCase.id).filter(WhistleCase.case_token == token).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_TOKEN_EXISTS)

    # 1. Lưu tệp bằng chứng (đã tẩy EXIF, chuẩn hóa tên/MIME) và lấy SHA-256 từng tệp
    try:
        stored = await evidence_service.store_uploads(files)
    except evidence_service.EvidenceRejected as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Không lưu được tệp bằng chứng: {exc}")

    # 2. Tính lại H trên server và xác minh chữ ký mù đã bóc
    fields = dict(
        category=category.strip(),
        encrypted_title=encrypted_title.strip(),
        encrypted_description=encrypted_description.strip(),
        case_token=token,
        case_public_key=case_public_key.strip(),
    )
    expected_h = BlindSignatureEngine.compute_payload_hash(
        **fields, evidence_file_hashes=[item.sha256 for item in stored]
    )
    raw_sig = unblinded_signature.strip()
    try:
        s = parse_rsa_int(raw_sig)
    except ValueError:
        evidence_service.discard(stored)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_SIG_FORMAT)
    if not BlindSignatureEngine.verify(expected_h, s):
        evidence_service.discard(stored)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_SIG_INVALID)

    # 3. Lưu hồ sơ (không có cột định danh nào; thời gian làm tròn theo giờ)
    bucket = _hour_bucket(datetime.now(timezone.utc))
    case = WhistleCase(
        **fields,
        payload_ephemeral_pub=payload_ephemeral_pub.strip(),
        payload_iv=payload_iv.strip(),
        payload_auth_tag=payload_auth_tag.strip(),
        unblinded_signature=raw_sig,
        status=CaseStatus.PENDING,
        created_bucket=bucket,
    )
    db.add(case)
    db.flush()
    for item in stored:
        db.add(CaseEvidence(case_id=case.id, file_url=item.file_url,
                            file_sha256_hash=item.sha256, mime_type=item.mime_type))
    db.commit()

    return CaseSubmitResponse(
        case_token=token,
        status=CaseStatus.PENDING,
        message="Hồ sơ tố giác ẩn danh đã được tiếp nhận và xác thực thành công.",
        created_bucket=bucket,
    )


@router.get("/cases/{case_token}", response_model=CaseStatusResponse)
def get_anonymous_case_status(case_token: str, db: Session = Depends(get_db)) -> CaseStatusResponse:
    """Tra cứu trạng thái hồ sơ và lịch sử chat E2EE bằng case_token."""
    case = (
        db.query(WhistleCase)
        .options(joinedload(WhistleCase.messages))
        .filter(WhistleCase.case_token == case_token.strip())
        .first()
    )
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_CASE_NOT_FOUND)

    messages = []
    for m in case.messages:
        view = CaseMessageResponse.model_validate(m)
        view.digital_signature = masked_signature_for_anonymous(m)
        messages.append(view)

    return CaseStatusResponse(
        case_token=case.case_token,
        category=case.category,
        status=case.status,
        created_bucket=case.created_bucket,
        # Không trả danh sách / đường dẫn tệp: người cầm mã hồ sơ không cần, và tệp chỉ Thanh tra xem được.
        evidences=[],
        messages=messages,
    )


@router.post("/cases/{case_token}/messages", response_model=CaseMessageResponse,
             status_code=status.HTTP_201_CREATED)
def send_anonymous_message(
    case_token: str,
    msg_in: MessageCreateRequest,
    db: Session = Depends(get_db),
) -> CaseMessageResponse:
    """Người tố giác gửi tin nhắn E2EE.

    Quyền sở hữu hồ sơ được chứng minh bằng chữ ký ECDSA P-256 (khóa riêng của hồ sơ)
    trên chuỗi `encrypted_message`, đối chiếu với `case_public_key` đã lưu khi nộp.
    """
    case = _find_case(db, case_token)
    try:
        pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), bytes.fromhex(case.case_public_key))
        pub_key.verify(bytes.fromhex(msg_in.digital_signature), msg_in.encrypted_message.encode("utf-8"),
                       ec.ECDSA(hashes.SHA256()))
    except (ValueError, InvalidSignature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ERR_OWNER_SIG)

    # Chống phát lại (replay): chữ ký ECDSA có thành phần ngẫu nhiên nên hai tin nhắn hợp lệ
    # không bao giờ trùng chữ ký; trùng = kẻ nghe lén gửi lại gói tin cũ.
    signature = msg_in.digital_signature.strip()
    if db.query(CaseMessage.id).filter(CaseMessage.case_id == case.id,
                                       CaseMessage.digital_signature == signature).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ERR_REPLAY)

    message = CaseMessage(
        case_id=case.id,
        sender_type=SenderType.WHISTLEBLOWER,
        ephemeral_pub_key=msg_in.ephemeral_pub_key.strip(),
        nonce_iv=msg_in.nonce_iv.strip(),
        encrypted_message=msg_in.encrypted_message.strip(),
        auth_tag=msg_in.auth_tag.strip(),
        digital_signature=signature,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return CaseMessageResponse.model_validate(message)
