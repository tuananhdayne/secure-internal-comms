from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.identified import User
from app.models.anonymous import WhistleCase, CaseMessage
from app.crypto.key_manager import key_manager
from app.crypto.ecies import ecies_decrypt
from app.schemas.officer import (
    OfficerCaseSummary,
    DecryptedCaseResponse,
    CaseStatusUpdate,
    OfficerReplyRequest
)
from app.schemas.anonymous import CaseEvidenceResponse, CaseMessageResponse
from app.api.deps import require_role

router = APIRouter(tags=["Officer Investigation"])


@router.get("/cases", response_model=List[OfficerCaseSummary])
def list_cases_for_investigation(
    current_user: User = Depends(require_role(["COMPLIANCE_OFFICER", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db)
) -> List[OfficerCaseSummary]:
    """Danh sách tất cả các vụ việc tố giác sai phạm dành cho Ban Thanh tra."""
    cases = db.query(WhistleCase).options(joinedload(WhistleCase.evidences)).order_by(WhistleCase.id.desc()).all()

    results = []
    for c in cases:
        results.append(OfficerCaseSummary(
            id=c.id,
            case_token=c.case_token,
            category=c.category,
            status=c.status,
            created_bucket=c.created_bucket,
            evidences_count=len(c.evidences)
        ))
    return results


@router.get("/cases/{case_id}/decrypt", response_model=DecryptedCaseResponse)
def decrypt_case_details(
    case_id: int,
    current_user: User = Depends(require_role(["COMPLIANCE_OFFICER", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db)
) -> DecryptedCaseResponse:
    """Ban Thanh tra sử dụng Khóa riêng ECC P-256 (Officer_Chat_PrivateKey) để giải mã hồ sơ tố giác.
    
    Chỉ duy nhất Ban Thanh tra mới sở hữu khóa riêng này. DBA và System Admin không thể xem nội dung.
    """
    case = db.query(WhistleCase).options(
        joinedload(WhistleCase.evidences),
        joinedload(WhistleCase.messages)
    ).filter(WhistleCase.id == case_id).first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hồ sơ tố giác không tồn tại."
        )

    # Giải mã ECIES
    try:
        decrypted_bytes = ecies_decrypt(
            recipient_priv_key=key_manager.ec_private_key,
            ephemeral_pub_hex=case.payload_ephemeral_pub,
            iv_hex=case.payload_iv,
            ciphertext_hex=case.encrypted_description,
            tag_hex=case.payload_auth_tag
        )
        decrypted_text = decrypted_bytes.decode("utf-8")
        if "|||" in decrypted_text:
            title, desc = decrypted_text.split("|||", 1)
        else:
            title = "Tiêu đề đã giải mã"
            desc = decrypted_text
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi giải mã hồ sơ: {str(e)}"
        )

    return DecryptedCaseResponse(
        id=case.id,
        case_token=case.case_token,
        category=case.category,
        status=case.status,
        decrypted_title=title,
        decrypted_description=desc,
        created_bucket=case.created_bucket,
        evidences=[CaseEvidenceResponse.model_validate(e) for e in case.evidences],
        messages=[CaseMessageResponse.model_validate(m) for m in case.messages]
    )


@router.patch("/cases/{case_id}/status", response_model=OfficerCaseSummary)
def update_case_status(
    case_id: int,
    status_in: CaseStatusUpdate,
    current_user: User = Depends(require_role(["COMPLIANCE_OFFICER", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db)
) -> OfficerCaseSummary:
    """Cập nhật trạng thái xử lý vụ việc (PENDING, INVESTIGATING, RESOLVED, REJECTED)."""
    case = db.query(WhistleCase).options(joinedload(WhistleCase.evidences)).filter(WhistleCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hồ sơ tố giác không tồn tại."
        )

    case.status = status_in.status.strip().upper()
    db.commit()
    db.refresh(case)

    return OfficerCaseSummary(
        id=case.id,
        case_token=case.case_token,
        category=case.category,
        status=case.status,
        created_bucket=case.created_bucket,
        evidences_count=len(case.evidences)
    )


@router.post("/cases/{case_id}/reply", response_model=CaseMessageResponse, status_code=status.HTTP_201_CREATED)
def reply_to_anonymous_whistleblower(
    case_id: int,
    reply_in: OfficerReplyRequest,
    current_user: User = Depends(require_role(["COMPLIANCE_OFFICER", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db)
) -> CaseMessageResponse:
    """Ban Thanh tra gửi tin nhắn điều tra E2EE tới người tố giác (sử dụng case_public_key của vụ việc)."""
    case = db.query(WhistleCase).filter(WhistleCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hồ sơ tố giác không tồn tại."
        )

    new_msg = CaseMessage(
        case_id=case.id,
        sender_type="COMPLIANCE_OFFICER",
        ephemeral_pub_key=reply_in.ephemeral_pub_key.strip(),
        nonce_iv=reply_in.nonce_iv.strip(),
        encrypted_message=reply_in.encrypted_message.strip(),
        auth_tag=reply_in.auth_tag.strip(),
        digital_signature=reply_in.digital_signature.strip()
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    return CaseMessageResponse.model_validate(new_msg)
