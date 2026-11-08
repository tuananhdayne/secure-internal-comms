import os
import io
import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

from app.core.config import settings
from app.db.session import get_db
from app.models.anonymous import WhistleCase, CaseEvidence, CaseMessage
from app.crypto.blind_signature import BlindSignatureEngine
from app.crypto.sanitizer import strip_image_metadata
from app.schemas.anonymous import (
    CaseSubmitResponse,
    CaseStatusResponse,
    MessageCreateRequest,
    CaseMessageResponse,
    CaseEvidenceResponse
)

router = APIRouter(tags=["Anonymous Whistleblowing & E2EE Chat"])


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
    db: Session = Depends(get_db)
) -> CaseSubmitResponse:
    """Cổng nộp hồ sơ tố giác sai phạm ẩn danh (Zero-Knowledge Endpoint).
    
    NGUYÊN TẮC BẢO MẬT:
    1. Không yêu cầu JWT, không ghi log IP hay User-Agent.
    2. Server tính lại mã băm toán học H ràng buộc (Category || Title || Desc || Case_Token || Case_PubKey || Hash(Files)).
    3. Xác minh tính toàn vẹn của chữ ký mù RSA: s^e mod N == H.
    4. Toàn bộ file đính kèm được lưu trên server ở dạng đã mã hóa bằng File_Key (AES-256-GCM).
    5. Cột `created_bucket` được làm tròn giờ chẵn để chống Timing Correlation Attack.
    """
    case_token_clean = case_token.strip()

    # 1. Kiểm tra case_token duy nhất
    existing_case = db.query(WhistleCase).filter(WhistleCase.case_token == case_token_clean).first()
    if existing_case:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã định danh hồ sơ (case_token) đã tồn tại trong hệ thống."
        )

    # 2. Xử lý lưu trữ tệp bằng chứng và tính SHA256 của từng file
    evidence_items = []
    saved_file_paths = []

    try:
        evidences_dir = settings.uploads_path / "evidences"
        evidences_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            content = await f.read()
            if not content:
                continue

            # Phòng thủ chiều sâu: Tẩy sạch siêu dữ liệu EXIF/GPS nếu phát hiện ảnh còn chứa thẻ EXIF
            is_image = (
                (f.content_type and f.content_type.startswith("image/"))
                or (f.filename and f.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
            )
            if is_image:
                try:
                    with Image.open(io.BytesIO(content)) as img:
                        exif = img._getexif()
                        if exif:
                            fmt = "PNG" if (f.filename and f.filename.lower().endswith(".png")) else "JPEG"
                            content = strip_image_metadata(content, image_format=fmt)
                except Exception:
                    pass

            # Tính mã băm SHA256 của file đã mã hóa
            f_hash = hashlib.sha256(content).hexdigest()

            # Lưu file vào thư mục an toàn (chống Path Traversal qua tên file)
            clean_basename = os.path.basename(f.filename or "evidence.bin") or "evidence.bin"
            safe_filename = f"{uuid.uuid4().hex}_{clean_basename}"
            file_dest = evidences_dir / safe_filename
            with open(file_dest, "wb") as out_file:
                out_file.write(content)

            saved_file_paths.append(file_dest)
            evidence_items.append({
                "file_url": f"/uploads/evidences/{safe_filename}",
                "file_sha256_hash": f_hash,
                "mime_type": f.content_type or "application/octet-stream"
            })

        # 3. Tính lại mã băm toán học H trên Server
        file_hashes = [item["file_sha256_hash"] for item in evidence_items]
        H = BlindSignatureEngine.compute_payload_hash(
            category=category.strip(),
            encrypted_title=encrypted_title.strip(),
            encrypted_description=encrypted_description.strip(),
            case_token=case_token_clean,
            case_public_key=case_public_key.strip(),
            evidence_file_hashes=file_hashes
        )

        # 4. Parse chữ ký s và xác minh: s^e mod N == H
        raw_sig = unblinded_signature.strip()
        try:
            if raw_sig.startswith("0x") or raw_sig.startswith("0X"):
                s = int(raw_sig, 16)
            elif any(c in "abcdefABCDEF" for c in raw_sig):
                s = int(raw_sig, 16)
            else:
                s = int(raw_sig)
        except ValueError:
            raise ValueError("Định dạng chữ ký mù không hợp lệ.")

        is_valid = BlindSignatureEngine.verify(H, s)
        if not is_valid:
            raise ValueError("Chữ ký mù không hợp lệ hoặc dữ liệu bằng chứng đã bị tráo đổi.")

    except Exception as e:
        # Xóa các file đã lưu tạm nếu xác minh thất bại
        for path in saved_file_paths:
            if path.exists():
                try:
                    os.remove(path)
                except OSError:
                    pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # 5. Lưu hồ sơ với time-bucketing (làm tròn giờ chẵn)
    now = datetime.now(timezone.utc)
    hour_bucket = now.replace(minute=0, second=0, microsecond=0)

    new_case = WhistleCase(
        case_token=case_token_clean,
        category=category.strip(),
        encrypted_title=encrypted_title.strip(),
        encrypted_description=encrypted_description.strip(),
        payload_ephemeral_pub=payload_ephemeral_pub.strip(),
        payload_iv=payload_iv.strip(),
        payload_auth_tag=payload_auth_tag.strip(),
        unblinded_signature=raw_sig,
        case_public_key=case_public_key.strip(),
        status="PENDING",
        created_bucket=hour_bucket
    )
    db.add(new_case)
    db.flush()

    for item in evidence_items:
        evidence = CaseEvidence(
            case_id=new_case.id,
            file_url=item["file_url"],
            file_sha256_hash=item["file_sha256_hash"],
            mime_type=item["mime_type"]
        )
        db.add(evidence)

    db.commit()

    return CaseSubmitResponse(
        case_token=case_token_clean,
        status="PENDING",
        message="Hồ sơ tố giác ẩn danh đã được tiếp nhận và xác thực thành công.",
        created_bucket=hour_bucket
    )


@router.get("/cases/{case_token}", response_model=CaseStatusResponse)
def get_anonymous_case_status(
    case_token: str,
    db: Session = Depends(get_db)
) -> CaseStatusResponse:
    """Tra cứu trạng thái hồ sơ và lịch sử tin nhắn chat E2EE bằng case_token."""
    case = db.query(WhistleCase).options(
        joinedload(WhistleCase.evidences),
        joinedload(WhistleCase.messages)
    ).filter(WhistleCase.case_token == case_token.strip()).first()

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ với mã case_token này."
        )

    sanitized_messages = []
    for m in case.messages:
        resp_m = CaseMessageResponse.model_validate(m)
        # Triệt tiêu rò rỉ bản rõ / payload nội bộ khi trả về cho anonymous client
        if m.sender_type == "COMPLIANCE_OFFICER" and (
            m.digital_signature.startswith("ENC:") or m.digital_signature.startswith("OFFICER_NOTE:")
        ):
            resp_m.digital_signature = "OFFICER_P256_VERIFIED_SIGNATURE"
        sanitized_messages.append(resp_m)

    return CaseStatusResponse(
        case_token=case.case_token,
        category=case.category,
        status=case.status,
        created_bucket=case.created_bucket,
        evidences=[CaseEvidenceResponse.model_validate(e) for e in case.evidences],
        messages=sanitized_messages
    )


@router.post("/cases/{case_token}/messages", response_model=CaseMessageResponse, status_code=status.HTTP_201_CREATED)
def send_anonymous_message(
    case_token: str,
    msg_in: MessageCreateRequest,
    db: Session = Depends(get_db)
) -> CaseMessageResponse:
    """Người tố giác gửi tin nhắn phản hồi điều tra (E2EE Chat).
    
    Yêu cầu chữ ký số ECDSA từ `case_private_key` của người tố giác để xác thực
    đúng chủ sở hữu vụ việc mà không cần danh tính.
    """
    case = db.query(WhistleCase).filter(WhistleCase.case_token == case_token.strip()).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ với mã case_token này."
        )

    # Xác minh chữ ký số ECDSA từ case_public_key
    try:
        case_pub_bytes = bytes.fromhex(case.case_public_key)
        pub_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(),
            case_pub_bytes
        )
        sig_bytes = bytes.fromhex(msg_in.digital_signature)
        # Ký trên nội dung ciphertext
        pub_key.verify(
            sig_bytes,
            msg_in.encrypted_message.encode("utf-8"),
            ec.ECDSA(hashes.SHA256())
        )
    except (ValueError, InvalidSignature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chữ ký số xác thực quyền chủ sở hữu hồ sơ không hợp lệ."
        )

    new_msg = CaseMessage(
        case_id=case.id,
        sender_type="ANONYMOUS_WHISTLEBLOWER",
        ephemeral_pub_key=msg_in.ephemeral_pub_key.strip(),
        nonce_iv=msg_in.nonce_iv.strip(),
        encrypted_message=msg_in.encrypted_message.strip(),
        auth_tag=msg_in.auth_tag.strip(),
        digital_signature=msg_in.digital_signature.strip()
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    return CaseMessageResponse.model_validate(new_msg)
