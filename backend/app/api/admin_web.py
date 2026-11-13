"""Web Admin Interface Router (Jinja2 + HTML5/CSS).
Dành riêng cho SYSTEM_ADMIN quản lý người dùng và bảng tin truyền thông nội bộ.

NGUYÊN TẮC BẢO MẬT & ZERO-KNOWLEDGE:
System Admin chỉ có quyền quản lý tài khoản định danh (Cụm 1) và bài viết nội bộ.
Admin TUYỆT ĐỐI KHÔNG CÓ THẨM QUYỀN giải mã hay xem chi tiết nội dung hồ sơ tố giác
ẩn danh (Cụm 2). Mọi nỗ lực can thiệp đều bị ngăn chặn bởi kiến trúc mật mã.
"""

from pathlib import Path
from typing import Optional
import logging
from fastapi import APIRouter, Depends, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.identified import User, Post, Comment
from app.models.anonymous import WhistleCase, CaseMessage, CaseEvidence
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.crypto.key_manager import key_manager
from app.crypto.ecies import ecies_decrypt, ecies_encrypt

logger = logging.getLogger(__name__)

# Khởi tạo Jinja2 Templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/admin", tags=["Web Admin Interface"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def admin_root(request: Request, db: Session = Depends(get_db)):
    """Chuyển hướng vào dashboard nếu đã đăng nhập, ngược lại vào login."""
    admin = get_current_admin(request, db)
    if admin:
        if admin.role == "COMPLIANCE_OFFICER":
            return RedirectResponse(url="/admin/cases", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Lấy thông tin SYSTEM_ADMIN hoặc COMPLIANCE_OFFICER từ Cookie admin_token (JWT)."""
    token = request.cookies.get("admin_token")
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id_str = payload.get("sub")
    role = payload.get("role")
    
    if not user_id_str or role not in ["SYSTEM_ADMIN", "COMPLIANCE_OFFICER"]:
        return None
    
    user = db.query(User).filter(User.id == int(user_id_str)).first()
    if not user or not user.is_active:
        return None
    
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    """Trang hiển thị form đăng nhập Admin & Thanh Tra."""
    admin = get_current_admin(request, db)
    if admin:
        if admin.role == "COMPLIANCE_OFFICER":
            return RedirectResponse(url="/admin/cases", status_code=status.HTTP_303_SEE_OTHER)
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
    """Xử lý xác thực đăng nhập Quản trị viên & Ban Thanh tra."""
    user = db.query(User).filter(User.employee_code == employee_code.strip()).first()
    
    if not user or not verify_password(password, user.password_hash) or user.role not in ["SYSTEM_ADMIN", "COMPLIANCE_OFFICER"]:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "error": "Mã nhân viên hoặc mật khẩu không chính xác hoặc không có quyền truy cập."
            },
            status_code=status.HTTP_200_OK
        )
    
    if not user.is_active:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "error": "Tài khoản này đã bị vô hiệu hóa."
            },
            status_code=status.HTTP_200_OK
        )
    
    # Tạo JWT Token
    token = create_access_token(subject=str(user.id), role=user.role)
    target_url = "/admin/cases" if user.role == "COMPLIANCE_OFFICER" else "/admin/dashboard"
    redirect = RedirectResponse(url=target_url, status_code=status.HTTP_303_SEE_OTHER)
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
    """Trang danh sách quản lý nhân sự (Chỉ dành cho SYSTEM_ADMIN)."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    if admin.role != "SYSTEM_ADMIN":
        return RedirectResponse(url="/admin/cases", status_code=status.HTTP_303_SEE_OTHER)
    
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
    """Tạo mới một tài khoản nhân sự (Chỉ dành cho SYSTEM_ADMIN)."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    if admin.role != "SYSTEM_ADMIN":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Truy cập bị từ chối: Chỉ Quản trị viên hệ thống mới được tạo tài khoản."}
        )
    
    valid_roles = {"EMPLOYEE", "COMPLIANCE_OFFICER", "BOARD_DIRECTOR", "SYSTEM_ADMIN"}
    role_clean = role.strip().upper()
    if role_clean not in valid_roles:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Vai trò không hợp lệ: {role}"}
        )

    existing = db.query(User).filter(User.employee_code == employee_code.strip()).first()
    if not existing:
        new_user = User(
            employee_code=employee_code.strip(),
            full_name=full_name.strip(),
            department=department.strip(),
            role=role_clean,
            password_hash=get_password_hash(password),
            is_active=True
        )
        db.add(new_user)
        db.commit()
    
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/toggle/{user_id}")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    """Khóa hoặc mở khóa tài khoản nhân viên (Chỉ dành cho SYSTEM_ADMIN)."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    if admin.role != "SYSTEM_ADMIN":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Truy cập bị từ chối: Chỉ Quản trị viên hệ thống mới được khóa/mở khóa tài khoản."}
        )
    
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


# --- CỤM 2: CỔNG THỤ LÝ & ĐIỀU TRA TUÂN THỦ (COMPLIANCE OFFICER) ---

@router.get("/cases", response_class=HTMLResponse)
def cases_page(request: Request, db: Session = Depends(get_db)):
    """Trang danh sách hồ sơ tố giác nặc danh dành cho Ban Thanh tra."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    if admin.role != "COMPLIANCE_OFFICER":
        return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    cases = db.query(WhistleCase).options(
        joinedload(WhistleCase.evidences),
        joinedload(WhistleCase.messages)
    ).order_by(WhistleCase.id.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="cases.html",
        context={
            "current_user": admin,
            "cases": cases
        }
    )


@router.get("/cases/{case_id}/decrypt", response_class=JSONResponse)
def decrypt_case_json(case_id: int, request: Request, db: Session = Depends(get_db)):
    """Giải mã hồ sơ ECIES bằng Officer Private Key."""
    admin = get_current_admin(request, db)
    if not admin:
        return JSONResponse(status_code=401, content={"error": "Chưa xác thực"})
    if admin.role != "COMPLIANCE_OFFICER":
        return JSONResponse(
            status_code=403,
            content={"error": "Truy cập bị từ chối: Chỉ Ban Thanh Tra mới có thẩm quyền giải mã hồ sơ."}
        )
    
    case = db.query(WhistleCase).options(
        joinedload(WhistleCase.evidences),
        joinedload(WhistleCase.messages)
    ).filter(WhistleCase.id == case_id).first()
    if not case:
        return JSONResponse(status_code=404, content={"error": "Không tìm thấy hồ sơ"})
    
    title = "[Giải mã thất bại]"
    description = "[Không thể giải mã bản rõ bằng Private Key hiện tại]"
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
            title, description = decrypted_text.split("|||", 1)
        else:
            title = "Tiêu đề hồ sơ"
            description = decrypted_text
    except Exception as e:
        logger.warning(f"Không thể giải mã nội dung hồ sơ {case_id}: {str(e)}")
    
    messages = []
    for m in case.messages:
        content = "[Nội dung mã hóa]"
        if m.sender_type == "COMPLIANCE_OFFICER":
            if m.digital_signature and m.digital_signature.startswith("ENC:"):
                # Giải mã bản sao của chính Officer bằng Officer Private Key
                try:
                    parts = m.digital_signature.split(":")
                    dec_bytes = ecies_decrypt(
                        recipient_priv_key=key_manager.ec_private_key,
                        ephemeral_pub_hex=parts[1],
                        iv_hex=parts[2],
                        ciphertext_hex=parts[3],
                        tag_hex=parts[4]
                    )
                    content = dec_bytes.decode("utf-8")
                except Exception as e:
                    logger.warning(f"Lỗi giải mã tin nhắn Officer {m.id}: {str(e)}")
                    content = "[Không thể giải mã tin nhắn phản hồi]"
            elif m.digital_signature and m.digital_signature.startswith("OFFICER_NOTE:"):
                # Tương thích ngược với các bản ghi cũ trước khi vá
                content = m.digital_signature.replace("OFFICER_NOTE:", "", 1)
            else:
                content = "Đã gửi thông báo điều tra E2EE đến người tố giác."
        else:
            # Người tố giác gửi tới Ban Thanh tra -> giải mã ECIES bằng Officer Private Key
            try:
                dec_bytes = ecies_decrypt(
                    recipient_priv_key=key_manager.ec_private_key,
                    ephemeral_pub_hex=m.ephemeral_pub_key,
                    iv_hex=m.nonce_iv,
                    ciphertext_hex=m.encrypted_message,
                    tag_hex=m.auth_tag
                )
                content = dec_bytes.decode("utf-8")
            except Exception as e:
                logger.warning(f"Lỗi giải mã tin nhắn tố giác {m.id}: {str(e)}")
                content = "[Tin nhắn mã hóa E2EE không thể giải mã]"

        messages.append({
            "id": m.id,
            "sender_type": m.sender_type,
            "content": content,
            "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return JSONResponse(content={
        "id": case.id,
        "case_token": case.case_token,
        "category": case.category,
        "status": case.status,
        "title": title,
        "description": description,
        "created_bucket": case.created_bucket.strftime("%Y-%m-%d %H:00:00 (UTC)"),
        "evidences": [{"id": e.id, "file_url": e.file_url, "mime_type": e.mime_type, "file_sha256_hash": e.file_sha256_hash} for e in case.evidences],
        "messages": messages
    })


@router.post("/cases/{case_id}/status")
def update_case_status_web(
    case_id: int,
    request: Request,
    new_status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Cập nhật trạng thái thụ lý vụ việc (Chỉ dành riêng cho COMPLIANCE_OFFICER)."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    if admin.role != "COMPLIANCE_OFFICER":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Truy cập bị từ chối: Chỉ Ban Thanh Tra mới có thẩm quyền cập nhật trạng thái hồ sơ."}
        )
    
    valid_statuses = {"PENDING", "INVESTIGATING", "UNDER_INVESTIGATION", "RESOLVED", "REJECTED"}
    status_clean = new_status.strip().upper()
    if status_clean not in valid_statuses:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Trạng thái không hợp lệ: {new_status}"}
        )

    case = db.query(WhistleCase).filter(WhistleCase.id == case_id).first()
    if case:
        case.status = status_clean
        db.commit()
    return RedirectResponse(url=f"/admin/cases?active_case_id={case_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/cases/{case_id}/reply")
def reply_case_web(
    case_id: int,
    request: Request,
    message: str = Form(...),
    db: Session = Depends(get_db)
):
    """Thanh tra viên gửi tin nhắn phản hồi đến người tố giác (Chỉ dành riêng cho COMPLIANCE_OFFICER)."""
    admin = get_current_admin(request, db)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    if admin.role != "COMPLIANCE_OFFICER":
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Truy cập bị từ chối: Chỉ Ban Thanh Tra mới có thẩm quyền gửi tin nhắn điều tra."}
        )
    
    msg_clean = message.strip()
    if not msg_clean:
        return RedirectResponse(url=f"/admin/cases?active_case_id={case_id}", status_code=status.HTTP_303_SEE_OTHER)

    case = db.query(WhistleCase).filter(WhistleCase.id == case_id).first()
    if not case:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "Hồ sơ không tồn tại"})

    try:
        # 1. Mã hóa ECIES bằng Public Key của hồ sơ tố giác (người tố giác dùng Private Key giải mã)
        enc_for_whistleblower = ecies_encrypt(case.case_public_key, msg_clean.encode("utf-8"))

        # 2. Mã hóa bản sao cho chính Officer bằng Officer Public Key (để xem lại an toàn trên web, không lộ bản rõ)
        enc_for_officer = ecies_encrypt(key_manager.ec_public_key_hex, msg_clean.encode("utf-8"))
        officer_sig_payload = f"ENC:{enc_for_officer['ephemeral_public_key']}:{enc_for_officer['iv']}:{enc_for_officer['ciphertext']}:{enc_for_officer['auth_tag']}"

        new_msg = CaseMessage(
            case_id=case.id,
            sender_type="COMPLIANCE_OFFICER",
            ephemeral_pub_key=enc_for_whistleblower["ephemeral_public_key"],
            nonce_iv=enc_for_whistleblower["iv"],
            encrypted_message=enc_for_whistleblower["ciphertext"],
            auth_tag=enc_for_whistleblower["auth_tag"],
            digital_signature=officer_sig_payload
        )
        db.add(new_msg)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Lỗi khi mã hóa hoặc ghi dữ liệu phản hồi vụ việc {case_id}: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Không thể gửi tin nhắn phản hồi do lỗi mã hóa hoặc cơ sở dữ liệu."}
        )

    return RedirectResponse(url=f"/admin/cases?active_case_id={case_id}", status_code=status.HTTP_303_SEE_OTHER)

