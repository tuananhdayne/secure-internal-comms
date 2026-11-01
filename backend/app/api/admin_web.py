"""Web Admin Interface Router (Jinja2 + HTML5/CSS).
Dành riêng cho SYSTEM_ADMIN quản lý người dùng và bảng tin truyền thông nội bộ.

NGUYÊN TẮC BẢO MẬT & ZERO-KNOWLEDGE:
System Admin chỉ có quyền quản lý tài khoản định danh (Cụm 1) và bài viết nội bộ.
Admin TUYỆT ĐỐI KHÔNG CÓ THẨM QUYỀN giải mã hay xem chi tiết nội dung hồ sơ tố giác
ẩn danh (Cụm 2). Mọi nỗ lực can thiệp đều bị ngăn chặn bởi kiến trúc mật mã.
"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.identified import User, Post, Comment
from app.models.anonymous import WhistleCase
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token

# Khởi tạo Jinja2 Templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin", tags=["Web Admin Interface"])


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Lấy thông tin SYSTEM_ADMIN từ Cookie admin_token (JWT)."""
    token = request.cookies.get("admin_token")
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id_str = payload.get("sub")
    role = payload.get("role")
    
    if not user_id_str or role != "SYSTEM_ADMIN":
        return None
    
    user = db.query(User).filter(User.id == int(user_id_str)).first()
    if not user or not user.is_active:
        return None
    
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    """Trang hiển thị form đăng nhập Admin."""
    admin = get_current_admin(request, db)
    if admin:
        return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"current_user": None, "error": None}
    )


@router.post("/login")
def login_submit(
    request: Request,
    response: Response,
    employee_code: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Xử lý xác thực đăng nhập Quản trị viên."""
    user = db.query(User).filter(User.employee_code == employee_code.strip()).first()
    
    if not user or not verify_password(password, user.password_hash) or user.role != "SYSTEM_ADMIN":
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "error": "Mã nhân viên hoặc mật khẩu quản trị không chính xác."
            },
            status_code=status.HTTP_200_OK
        )
    
    if not user.is_active:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "error": "Tài khoản quản trị viên này đã bị vô hiệu hóa."
            },
            status_code=status.HTTP_200_OK
        )
    
    # Tạo JWT Token
    token = create_access_token(subject=str(user.id), role=user.role)
    redirect = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )
    return redirect


@router.get("/logout")
def logout():
    """Đăng xuất Quản trị viên."""
    redirect = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(key="admin_token")
    return redirect


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Trang Dashboard tổng quan hệ thống."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    stats = {
        "total_users": db.query(User).count(),
        "officer_users": db.query(User).filter(User.role == "COMPLIANCE_OFFICER").count(),
        "total_posts": db.query(Post).count(),
        "total_comments": db.query(Comment).count(),
        "total_cases": db.query(WhistleCase).count()
    }
    
    latest_posts = db.query(Post).order_by(Post.created_at.desc()).limit(5).all()
    
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "current_user": admin,
            "stats": stats,
            "latest_posts": latest_posts
        }
    )


@router.get("/users", response_class=HTMLResponse)
def users_list(request: Request, db: Session = Depends(get_db)):
    """Trang danh sách quản lý nhân sự."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    users = db.query(User).order_by(User.id.asc()).all()
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "current_user": admin,
            "users": users
        }
    )


@router.post("/users/create")
def create_user(
    request: Request,
    employee_code: str = Form(...),
    full_name: str = Form(...),
    department: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Tạo mới một tài khoản nhân sự."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    existing = db.query(User).filter(User.employee_code == employee_code.strip()).first()
    if not existing:
        new_user = User(
            employee_code=employee_code.strip(),
            full_name=full_name.strip(),
            department=department.strip(),
            role=role.strip(),
            password_hash=get_password_hash(password),
            is_active=True
        )
        db.add(new_user)
        db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/toggle/{user_id}")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    """Khóa hoặc mở khóa tài khoản nhân viên."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.role != "SYSTEM_ADMIN":
        target_user.is_active = not target_user.is_active
        db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/posts", response_class=HTMLResponse)
def posts_list(request: Request, db: Session = Depends(get_db)):
    """Trang quản trị bài viết nội bộ."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="posts.html",
        context={
            "current_user": admin,
            "posts": posts
        }
    )


@router.post("/posts/create")
def create_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    is_pinned: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Admin đăng bài viết thông báo mới."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    new_post = Post(
        title=title.strip(),
        content=content.strip(),
        author_id=admin.id,
        is_pinned=(is_pinned == "true")
    )
    db.add(new_post)
    db.commit()
    
    return RedirectResponse(url="/admin/posts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/posts/delete/{post_id}")
def delete_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    """Admin xóa bài viết nội bộ."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    target_post = db.query(Post).filter(Post.id == post_id).first()
    if target_post:
        db.delete(target_post)
        db.commit()
    
    return RedirectResponse(url="/admin/posts", status_code=status.HTTP_303_SEE_OTHER)
