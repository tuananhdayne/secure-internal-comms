"""Web Admin (Jinja2 SSR) cho SYSTEM_ADMIN và COMPLIANCE_OFFICER.

Bản đồ route (prefix /admin):

    Phiên đăng nhập      GET  /login, POST /login, GET /logout, GET /
    Cụm 1 (Admin)        GET  /dashboard           (mọi vai trò web)
                         GET  /users               POST /users/create, /users/toggle/{id}
                         GET  /posts (mọi vai trò)  POST /posts/create, /posts/delete/{id}
    Cụm 2 (Thanh tra)    GET  /cases               GET  /cases/{id}/decrypt (JSON)
                         POST /cases/{id}/status   POST /cases/{id}/reply

Phân quyền: cookie `admin_token` (JWT, HttpOnly) -> `get_current_admin()`; mỗi route gọi
`_guard()` với tập vai trò được phép. System Admin KHÔNG có quyền giải mã hồ sơ (Cụm 2);
nghiệp vụ mật mã nằm ở `app.services.case_crypto`.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Iterable, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.constants import CaseStatus, Role
from app.core.permissions import PRIVILEGED_ROLES, WEB_ASSIGNABLE_ROLES, Perm, has_permission
from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.anonymous import WhistleCase
from app.models.identified import Comment, Post, User
from app.services.login_throttle import lockout_message, login_throttle
from app.services.case_crypto import build_officer_reply, decrypt_case_payload, officer_message_view

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(settings.templates_dir))

try:
    _DISPLAY_TZ = ZoneInfo(settings.DISPLAY_TIMEZONE)
except ZoneInfoNotFoundError:
    _DISPLAY_TZ = timezone.utc


def _local_dt(value: Optional[datetime], fmt: str = "%d/%m/%Y %H:%M") -> str:
    """Đổi thời điểm UTC (naive hoặc aware) trong CSDL sang múi giờ hiển thị."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_DISPLAY_TZ).strftime(fmt)


# Ứng dụng di động tự đính kèm một tệp giữ chỗ khi người dùng không chọn bằng chứng nào
# (để ràng buộc chữ ký). Tệp này không có giá trị với cán bộ nên ẩn khỏi giao diện.
_PLACEHOLDER_EVIDENCE = re.compile(r"(?:^|/)(?:[0-9a-f]{32}_)?evidence_\d+\.bin$")


def _real_evidences(evidences: Iterable) -> list:
    return [e for e in evidences if not _PLACEHOLDER_EVIDENCE.search(getattr(e, "file_url", "") or "")]


def _case_code(token: Optional[str]) -> str:
    """Mã hồ sơ rút gọn, khớp với mã hiển thị trên ứng dụng: 6 ký tự chữ/số cuối, viết hoa."""
    alnum = re.sub(r"[^A-Za-z0-9]", "", token or "")
    return "#" + alnum[-6:].upper()


templates.env.filters["local_dt"] = _local_dt
templates.env.filters["real_evidences"] = _real_evidences
templates.env.filters["case_code"] = _case_code
templates.env.globals["can"] = has_permission  # template: {% if can(current_user.role, "post.manage") %}
templates.env.globals["Perm"] = Perm
templates.env.globals["show_demo_accounts"] = settings.SHOW_DEMO_ACCOUNTS
router = APIRouter(prefix="/admin", tags=["Web Admin Interface"])

COOKIE_NAME = "admin_token"
DENY_PREFIX = "Truy cập bị từ chối: "


# ============================================================================
# Phiên đăng nhập & phân quyền
# ============================================================================

def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Người dùng web hiện tại từ cookie JWT, hoặc None nếu chưa đăng nhập / token không hợp lệ.

    Vai trò luôn được kiểm lại theo CSDL (token có thể đã cũ nếu tài khoản bị đổi vai trò / khóa).
    """
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_access_token(token) if token else None
    if not payload or not has_permission(payload.get("role", ""), Perm.WEB_PORTAL):
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or not has_permission(user.role, Perm.WEB_PORTAL):
        return None
    return user


def _home_url(user: User) -> str:
    """Trang đầu tiên theo quyền của vai trò."""
    if has_permission(user.role, Perm.CASE_MANAGE):
        return "/admin/cases"
    if has_permission(user.role, Perm.USER_MANAGE):
        return "/admin/dashboard"
    return "/admin/stats"


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _forbidden(reason: str) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": DENY_PREFIX + reason})


def _guard(
    request: Request,
    db: Session,
    perm: str = Perm.WEB_PORTAL,
    *,
    page: bool = False,
    deny_reason: Optional[str] = None,
) -> Tuple[Optional[User], Optional[Response]]:
    """Kiểm tra đăng nhập + quyền (theo app/core/permissions.py) cho một route web.

    Trả về (user, None) nếu được phép; ngược lại (None, response) để route `return` ngay:
    - chưa đăng nhập -> chuyển về /admin/login
    - thiếu quyền    -> trang GET (`page=True`): về trang đầu của vai trò; thao tác: JSON 403
    """
    user = get_current_admin(request, db)
    if not user:
        return None, _redirect("/admin/login")
    if not has_permission(user.role, perm):
        if page:
            return None, _redirect(_home_url(user))
        return None, _forbidden(deny_reason or "Bạn không có quyền thực hiện thao tác này.")
    return user, None


def _render(request: Request, name: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name=name, context=context)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def admin_root(request: Request, db: Session = Depends(get_db)):
    user = get_current_admin(request, db)
    return _redirect(_home_url(user) if user else "/admin/login")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_admin(request, db)
    if user:
        return _redirect(_home_url(user))
    return _render(request, "login.html", current_user=None, error=None)


@router.post("/login")
def login_submit(
    request: Request,
    employee_code: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Xác thực Quản trị viên / Thanh tra và đặt cookie JWT."""
    code = employee_code.strip()
    retry_after = login_throttle.retry_after(code)
    if retry_after:
        response = _render(request, "login.html", current_user=None, error=lockout_message(retry_after))
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        response.headers["Retry-After"] = str(retry_after)
        return response

    user = db.query(User).filter(User.employee_code == code).first()
    if not user or not verify_password(password, user.password_hash) or not has_permission(user.role, Perm.WEB_PORTAL):
        login_throttle.record_failure(code)
        return _render(request, "login.html", current_user=None,
                       error="Mã nhân viên hoặc mật khẩu không chính xác hoặc không có quyền truy cập.")
    if not user.is_active:
        return _render(request, "login.html", current_user=None, error="Tài khoản này đã bị vô hiệu hóa.")
    login_throttle.record_success(code)

    response = _redirect(_home_url(user))
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(subject=str(user.id), role=user.role),
        httponly=True,
        secure=request.url.scheme == "https",  # chỉ gửi qua TLS khi chạy run_https.py
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # khớp thời hạn JWT
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = _redirect("/admin/login")
    response.delete_cookie(key=COOKIE_NAME)
    return response


# ============================================================================
# Cụm 1: Tổng quan, Nhân sự, Truyền thông (SYSTEM_ADMIN)
# ============================================================================

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user, denied = _guard(request, db, Perm.USER_MANAGE, page=True)
    if denied:
        return denied
    # Quản trị không có quyền thống kê tố giác (tách bạch nhiệm vụ) -> không hiển thị số hồ sơ.
    stats = {
        "total_users": db.query(User).count(),
        "officer_users": db.query(User).filter(User.role == Role.COMPLIANCE_OFFICER).count(),
        "locked_users": db.query(User).filter(User.is_active.is_(False)).count(),
        "total_posts": db.query(Post).count(),
        "total_comments": db.query(Comment).count(),
    }
    latest_posts = db.query(Post).order_by(Post.created_at.desc()).limit(5).all()
    return _render(request, "dashboard.html", current_user=user, stats=stats, latest_posts=latest_posts)


@router.get("/users", response_class=HTMLResponse)
def users_list(request: Request, db: Session = Depends(get_db)):
    user, denied = _guard(request, db, Perm.USER_MANAGE, page=True)
    if denied:
        return denied
    users = db.query(User).order_by(User.id.asc()).all()
    return _render(request, "users.html", current_user=user, users=users,
                   privileged_roles=PRIVILEGED_ROLES)


@router.post("/users/create")
def create_user(
    request: Request,
    employee_code: str = Form(...),
    full_name: str = Form(...),
    department: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    _, denied = _guard(request, db, Perm.USER_MANAGE,
                       deny_reason="Chỉ Quản trị viên hệ thống mới được tạo tài khoản.")
    if denied:
        return denied

    role_clean = role.strip().upper()
    if role_clean not in Role.ALL:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": f"Vai trò không hợp lệ: {role}"})
    if role_clean not in WEB_ASSIGNABLE_ROLES:
        # Vai trò Thanh tra / Quản trị chỉ cấp qua scripts/manage_roles.py trên máy chủ.
        return _forbidden("Vai trò này không thể cấp qua cổng web.")

    code = employee_code.strip()
    if not db.query(User).filter(User.employee_code == code).first():
        db.add(User(
            employee_code=code,
            full_name=full_name.strip(),
            department=department.strip(),
            role=role_clean,
            password_hash=get_password_hash(password),
            is_active=True,
        ))
        db.commit()
    return _redirect("/admin/users")


@router.post("/users/toggle/{user_id}")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    """Khóa / mở khóa tài khoản Nhân viên & Ban Giám đốc.

    Tài khoản Thanh tra / Quản trị chỉ quản lý qua scripts/manage_roles.py (tránh việc Quản trị
    vô hiệu hóa toàn bộ Ban Thanh tra từ web).
    """
    _, denied = _guard(request, db, Perm.USER_MANAGE,
                       deny_reason="Chỉ Quản trị viên hệ thống mới được khóa/mở khóa tài khoản.")
    if denied:
        return denied
    target = db.query(User).filter(User.id == user_id).first()
    if target and target.role not in WEB_ASSIGNABLE_ROLES:
        return _forbidden("Tài khoản này chỉ được quản lý trên máy chủ.")
    if target:
        target.is_active = not target.is_active
        db.commit()
    return _redirect("/admin/users")


@router.get("/posts", response_class=HTMLResponse)
def posts_list(request: Request, db: Session = Depends(get_db)):
    user, denied = _guard(request, db, Perm.POST_MANAGE, page=True)
    if denied:
        return denied
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return _render(request, "posts.html", current_user=user, posts=posts)


@router.post("/posts/create")
def create_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    is_pinned: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user, denied = _guard(request, db, Perm.POST_MANAGE, deny_reason="Chỉ Quản trị viên hệ thống mới được đăng bài.")
    if denied:
        return denied
    db.add(Post(title=title.strip(), content=content.strip(), author_id=user.id, is_pinned=(is_pinned == "true")))
    db.commit()
    return _redirect("/admin/posts")


@router.post("/posts/delete/{post_id}")
def delete_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    _, denied = _guard(request, db, Perm.POST_MANAGE, deny_reason="Chỉ Quản trị viên hệ thống mới được xóa bài.")
    if denied:
        return denied
    target = db.query(Post).filter(Post.id == post_id).first()
    if target:
        db.delete(target)
        db.commit()
    return _redirect("/admin/posts")


# ============================================================================
# Thống kê tố giác (Ban Giám đốc, Thanh tra) — CHỈ số lượng, không có nội dung
# ============================================================================

@router.get("/stats", response_class=HTMLResponse)
def case_stats(request: Request, db: Session = Depends(get_db)):
    user, denied = _guard(request, db, Perm.CASE_STATS, page=True)
    if denied:
        return denied
    from sqlalchemy import func

    def _norm(st: str) -> str:
        return CaseStatus.INVESTIGATING if st == CaseStatus.UNDER_INVESTIGATION else st

    by_status: dict = {}
    for st, n in db.query(WhistleCase.status, func.count()).group_by(WhistleCase.status).all():
        by_status[_norm(st)] = by_status.get(_norm(st), 0) + n
    by_category = (
        db.query(WhistleCase.category, func.count())
        .group_by(WhistleCase.category)
        .order_by(func.count().desc())
        .all()
    )
    by_month: dict = {}
    for (bucket,) in db.query(WhistleCase.created_bucket).all():
        key = _local_dt(bucket, "%m/%Y")
        by_month[key] = by_month.get(key, 0) + 1
    return _render(
        request, "stats.html", current_user=user,
        total=sum(by_status.values()), by_status=by_status,
        by_category=by_category, by_month=sorted(by_month.items(), key=lambda kv: kv[0][3:] + kv[0][:2]),
    )


# ============================================================================
# Cụm 2: Cổng Thanh tra (COMPLIANCE_OFFICER)
# ============================================================================

def _case_url(case_id: int) -> str:
    """Quay lại trang hồ sơ và tự mở lại modal của vụ việc."""
    return f"/admin/cases?active_case_id={case_id}"


@router.get("/cases", response_class=HTMLResponse)
def cases_page(request: Request, db: Session = Depends(get_db)):
    user, denied = _guard(request, db, Perm.CASE_MANAGE, page=True)
    if denied:
        return denied
    cases = (
        db.query(WhistleCase)
        .options(joinedload(WhistleCase.evidences), joinedload(WhistleCase.messages))
        .order_by(WhistleCase.id.desc())
        .all()
    )
    return _render(request, "cases.html", current_user=user, cases=cases)


@router.get("/cases/{case_id}/decrypt", response_class=JSONResponse)
def decrypt_case_json(case_id: int, request: Request, db: Session = Depends(get_db)):
    """JSON cho modal thụ lý: bản rõ hồ sơ, bằng chứng và tin nhắn đã giải mã."""
    user = get_current_admin(request, db)
    if not user:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": "Chưa xác thực"})
    if not has_permission(user.role, Perm.CASE_MANAGE):
        return _forbidden("Chỉ Ban Thanh Tra mới có thẩm quyền giải mã hồ sơ.")

    case = (
        db.query(WhistleCase)
        .options(joinedload(WhistleCase.evidences), joinedload(WhistleCase.messages))
        .filter(WhistleCase.id == case_id)
        .first()
    )
    if not case:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "Không tìm thấy hồ sơ"})

    plain = decrypt_case_payload(case)
    return JSONResponse(content={
        "id": case.id,
        "case_token": case.case_token,
        "category": case.category,
        "status": case.status,
        "title": plain.title,
        "description": plain.description,
        "decrypted": plain.ok,
        "created_bucket": case.created_bucket.strftime("%Y-%m-%d %H:00:00 (UTC)"),
        "evidences": [
            {"id": e.id, "file_url": e.file_url, "mime_type": e.mime_type, "file_sha256_hash": e.file_sha256_hash}
            for e in case.evidences
        ],
        "messages": [officer_message_view(m) for m in case.messages],
    })


@router.post("/cases/{case_id}/status")
def update_case_status_web(
    case_id: int,
    request: Request,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
):
    _, denied = _guard(request, db, Perm.CASE_MANAGE,
                       deny_reason="Chỉ Ban Thanh Tra mới có thẩm quyền cập nhật trạng thái hồ sơ.")
    if denied:
        return denied
    status_clean = new_status.strip().upper()
    if status_clean not in CaseStatus.ALL:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error": f"Trạng thái không hợp lệ: {new_status}"})
    case = db.query(WhistleCase).filter(WhistleCase.id == case_id).first()
    if case:
        case.status = status_clean
        db.commit()
    return _redirect(_case_url(case_id))


@router.post("/cases/{case_id}/reply")
def reply_case_web(
    case_id: int,
    request: Request,
    message: str = Form(...),
    db: Session = Depends(get_db),
):
    """Thanh tra gửi phản hồi: server mã hóa ECIES tới khóa công khai của hồ sơ."""
    _, denied = _guard(request, db, Perm.CASE_MANAGE,
                       deny_reason="Chỉ Ban Thanh Tra mới có thẩm quyền gửi tin nhắn điều tra.")
    if denied:
        return denied
    text = message.strip()
    if not text:
        return _redirect(_case_url(case_id))
    case = db.query(WhistleCase).filter(WhistleCase.id == case_id).first()
    if not case:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "Hồ sơ không tồn tại"})
    try:
        db.add(build_officer_reply(case, text))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Lỗi mã hóa / ghi phản hồi cho hồ sơ id=%s", case_id)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            content={"error": "Không thể gửi tin nhắn phản hồi do lỗi mã hóa hoặc cơ sở dữ liệu."})
    return _redirect(_case_url(case_id))
