from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import get_db
from app.models.identified import User, BlindSignQuota
from app.crypto.key_manager import key_manager
from app.crypto.blind_signature import BlindSignatureEngine
from app.schemas.compliance import OfficerKeysResponse, BlindSignRequest, BlindSignResponse
from app.api.deps import get_current_user

router = APIRouter(tags=["Compliance & Blind Signatures"])


@router.get("/public-keys", response_model=OfficerKeysResponse)
def get_public_keys() -> OfficerKeysResponse:
    """Công khai cặp khóa công khai của Ban Thanh tra:
    1. RSA-2048 (e, n): Phục vụ thuật toán ký mù bảo đảm tính toàn vẹn và vô danh.
    2. ECC P-256 (chat_pub_hex): Phục vụ mã hóa ECIES nội dung hồ sơ và tin nhắn E2EE.
    """
    e, n = key_manager.rsa_public_numbers
    return OfficerKeysResponse(
        blind_sign_pub={
            "e": hex(e),
            "n": hex(n)
        },
        chat_pub_hex=key_manager.ec_public_key_hex
    )


@router.post("/blind-sign", response_model=BlindSignResponse)
def request_blind_signature(
    req: BlindSignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> BlindSignResponse:
    """Cấp phát chữ ký mù RSA cho nhân viên hợp lệ (Áp dụng Quota hàng tuần).
    
    NGUYÊN TẮC BẢO MẬT TUYỆT ĐỐI (UNLINKABILITY):
    - Server chỉ nhận m* = (H * r^e) mod N đã được làm mù hoàn toàn.
    - Ban Thanh tra không biết nội dung H bên dưới và không thể suy ra chữ ký s sau này.
    - Hệ thống chỉ đếm số lượt `request_count`, TUYỆT ĐỐI KHÔNG GHI THỜI GIAN (timestamp)
      vào bảng `blind_sign_quotas` để triệt tiêu đòn tấn công Timing Correlation.
    """
    # 1. Tính mã tuần hiện tại (YYYYWW), ví dụ: 202644
    now = datetime.now(timezone.utc)
    week_epoch = int(now.strftime("%Y%W"))

    # 2. Truy vấn hạn mức trong tuần
    quota = db.query(BlindSignQuota).filter(
        BlindSignQuota.user_id == current_user.id,
        BlindSignQuota.week_epoch == week_epoch
    ).first()

    if not quota:
        try:
            quota = BlindSignQuota(
                user_id=current_user.id,
                week_epoch=week_epoch,
                request_count=0
            )
            db.add(quota)
            db.commit()
            db.refresh(quota)
        except IntegrityError:
            db.rollback()
            quota = db.query(BlindSignQuota).filter(
                BlindSignQuota.user_id == current_user.id,
                BlindSignQuota.week_epoch == week_epoch
            ).first()

    if quota and quota.request_count >= settings.WEEKLY_BLIND_SIGN_QUOTA:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Bạn đã vượt quá hạn mức xin chữ ký mù trong tuần (Tối đa {settings.WEEKLY_BLIND_SIGN_QUOTA} lượt/tuần)."
        )

    # 3. Parse m* từ hex hoặc chuỗi số nguyên
    raw_blinded = req.blinded_hash.strip()
    try:
        if raw_blinded.startswith("0x") or raw_blinded.startswith("0X"):
            m_star = int(raw_blinded, 16)
        elif any(c in "abcdefABCDEF" for c in raw_blinded):
            m_star = int(raw_blinded, 16)
        else:
            m_star = int(raw_blinded)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giá trị băm làm mù (blinded_hash) không đúng định dạng."
        )

    # 4. Ký mù RSA: s* = (m*)^d mod N
    try:
        s_star = BlindSignatureEngine.blind_sign(m_star)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # 5. Tăng lượt ký và commit (Không cập nhật timestamp)
    quota.request_count += 1
    db.commit()

    return BlindSignResponse(
        blind_signature=hex(s_star),
        remaining_quota=settings.WEEKLY_BLIND_SIGN_QUOTA - quota.request_count
    )
