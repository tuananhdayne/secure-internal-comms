"""Cụm 2 — REST API cho Ban Thanh tra (JWT, vai trò COMPLIANCE_OFFICER).

Web Admin dùng cùng nghiệp vụ qua `app.services.case_crypto`; module này chỉ lo HTTP.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_permission
from app.core.permissions import Perm
from app.core.constants import CaseStatus, Role, SenderType
from app.db.session import get_db
from app.models.anonymous import CaseEvidence, CaseMessage, WhistleCase
from app.models.identified import User
from app.schemas.anonymous import CaseEvidenceResponse, CaseMessageResponse
from app.schemas.officer import CaseStatusUpdate, DecryptedCaseResponse, OfficerCaseSummary, OfficerReplyRequest
from app.services.case_crypto import decrypt_case_payload
from app.services.evidence import evidence_response, is_placeholder
from app.core.config import settings
from app.services.audit import Action, record as audit

router = APIRouter(tags=["Officer Investigation"])
officer_only = require_permission(Perm.CASE_MANAGE)

ERR_CASE_NOT_FOUND = "Hồ sơ tố giác không tồn tại."


def _get_case(db: Session, case_id: int, *, with_children: bool = False) -> WhistleCase:
    query = db.query(WhistleCase)
    query = query.options(joinedload(WhistleCase.evidences))
    if with_children:
        query = query.options(joinedload(WhistleCase.messages))
    case = query.filter(WhistleCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERR_CASE_NOT_FOUND)
    return case


def _summary(case: WhistleCase) -> OfficerCaseSummary:
    return OfficerCaseSummary(
        id=case.id,
        case_token=case.case_token,
        category=case.category,
        status=case.status,
        created_bucket=case.created_bucket,
        evidences_count=len(case.evidences),
    )


@router.get("/cases", response_model=List[OfficerCaseSummary])
def list_cases_for_investigation(
    current_user: User = Depends(officer_only),
    db: Session = Depends(get_db),
) -> List[OfficerCaseSummary]:
    """Danh sách tất cả hồ sơ tố giác (mới nhất trước)."""
    cases = db.query(WhistleCase).options(joinedload(WhistleCase.evidences)).order_by(WhistleCase.id.desc()).all()
    return [_summary(c) for c in cases]


@router.get("/cases/{case_id}/decrypt", response_model=DecryptedCaseResponse)
def decrypt_case_details(
    case_id: int,
    current_user: User = Depends(officer_only),
    db: Session = Depends(get_db),
) -> DecryptedCaseResponse:
    """Giải mã hồ sơ bằng khóa riêng EC của Ban Thanh tra (DBA / Admin không có khóa này)."""
    case = _get_case(db, case_id, with_children=True)
    plain = decrypt_case_payload(case)
    audit(db, current_user, Action.CASE_VIEW, f"case:{case.id}")
    if not plain.ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Lỗi giải mã hồ sơ: {plain.error}")
    return DecryptedCaseResponse(
        id=case.id,
        case_token=case.case_token,
        category=case.category,
        status=case.status,
        decrypted_title=plain.title,
        decrypted_description=plain.description,
        created_bucket=case.created_bucket,
        evidences=[
            CaseEvidenceResponse(id=e.id, file_url=f"{settings.API_V1_STR}/officer/evidence/{e.id}",
                                 file_sha256_hash=e.file_sha256_hash, mime_type=e.mime_type)
            for e in case.evidences if not is_placeholder(e.file_url, e.mime_type)
        ],
        messages=[CaseMessageResponse.model_validate(m) for m in case.messages],
    )


@router.patch("/cases/{case_id}/status", response_model=OfficerCaseSummary)
def update_case_status(
    case_id: int,
    status_in: CaseStatusUpdate,
    current_user: User = Depends(officer_only),
    db: Session = Depends(get_db),
) -> OfficerCaseSummary:
    """Cập nhật trạng thái thụ lý (giá trị hợp lệ: `CaseStatus.ALL`)."""
    case = _get_case(db, case_id)
    new_status = status_in.status.strip().upper()
    if new_status not in CaseStatus.ALL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Trạng thái không hợp lệ: {new_status}")
    old = case.status
    case.status = new_status
    db.commit()
    audit(db, current_user, Action.CASE_STATUS, f"case:{case.id}", f"{old} → {new_status}")
    db.refresh(case)
    return _summary(case)


@router.post("/cases/{case_id}/reply", response_model=CaseMessageResponse, status_code=status.HTTP_201_CREATED)
def reply_to_anonymous_whistleblower(
    case_id: int,
    reply_in: OfficerReplyRequest,
    current_user: User = Depends(officer_only),
    db: Session = Depends(get_db),
) -> CaseMessageResponse:
    """Lưu tin nhắn E2EE mà client của Thanh tra đã tự mã hóa tới `case_public_key`."""
    case = _get_case(db, case_id)
    message = CaseMessage(
        case_id=case.id,
        sender_type=SenderType.OFFICER,
        ephemeral_pub_key=reply_in.ephemeral_pub_key.strip(),
        nonce_iv=reply_in.nonce_iv.strip(),
        encrypted_message=reply_in.encrypted_message.strip(),
        auth_tag=reply_in.auth_tag.strip(),
        digital_signature=reply_in.digital_signature.strip(),
    )
    db.add(message)
    db.commit()
    audit(db, current_user, Action.CASE_REPLY, f"case:{case.id}")
    db.refresh(message)
    return CaseMessageResponse.model_validate(message)


@router.get("/evidence/{evidence_id}")
def download_evidence(
    evidence_id: int,
    download: int = 0,
    current_user: User = Depends(officer_only),
    db: Session = Depends(get_db),
):
    """Tải tệp bằng chứng đã giải mã (chỉ Cán bộ Thanh tra)."""
    ev = db.query(CaseEvidence).filter(CaseEvidence.id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tệp bằng chứng.")
    try:
        resp = evidence_response(ev.file_url, ev.mime_type, download=bool(download))
        audit(db, current_user, Action.EVIDENCE_DOWNLOAD, f"case:{ev.case_id}", f"tệp #{ev.id}")
        return resp
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tệp bằng chứng không khả dụng.")
