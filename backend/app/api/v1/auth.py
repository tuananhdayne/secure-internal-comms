from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.identified import User
from app.core.security import verify_password, create_access_token
from app.schemas.auth import TokenResponse, UserResponse
from app.api.deps import get_current_user
from app.core.permissions import Perm, has_permission
from app.services.login_throttle import lockout_message, login_throttle

router = APIRouter(tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> TokenResponse:
    """Đăng nhập hệ thống bằng Mã nhân viên (employee_code) và Mật khẩu.
    
    Tương thích chuẩn OAuth2 Password Bearer cho Swagger UI và Android Client.
    """
    employee_code = form_data.username.strip()

    retry_after = login_throttle.retry_after(employee_code)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=lockout_message(retry_after),
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.employee_code == employee_code).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        login_throttle.record_failure(employee_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã nhân viên hoặc mật khẩu không chính xác."
        )

    # Mật khẩu đúng nhưng không được dùng ứng dụng: tài khoản bị khóa, hoặc tài khoản
    # Quản trị (chỉ dùng cổng web, không đọc bảng tin / không gửi tố giác).
    if not user.is_active or not has_permission(user.role, Perm.APP_ACCESS):
        login_throttle.record_success(employee_code)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này không thể đăng nhập ứng dụng. Vui lòng liên hệ Quản trị viên."
        )

    login_throttle.record_success(employee_code)

    # Sinh JWT Access Token
    access_token = create_access_token(
        subject=str(user.id),
        role=user.role
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user.role
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Lấy thông tin hồ sơ của người dùng đang đăng nhập."""
    return UserResponse.model_validate(current_user)
