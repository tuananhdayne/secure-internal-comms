from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.identified import User
from app.core.security import verify_password, create_access_token
from app.schemas.auth import TokenResponse, UserResponse
from app.api.deps import get_current_user

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
    user = db.query(User).filter(User.employee_code == employee_code).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã nhân viên hoặc mật khẩu không chính xác."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản nhân viên này đang bị vô hiệu hóa."
        )

    # Sinh JWT Access Token
    access_token = create_access_token(
        subject=str(user.id),
        role=user.role
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Lấy thông tin hồ sơ của người dùng đang đăng nhập."""
    return UserResponse.model_validate(current_user)
