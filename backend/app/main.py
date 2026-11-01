import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.session import engine, Base
from app.crypto.key_manager import key_manager
from app.api.v1 import auth, posts, compliance, anonymous, officer
from app.api import admin_web


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Khởi tạo tài nguyên hệ thống khi server startup."""
    # 1. Khởi tạo Database Tables
    Base.metadata.create_all(bind=engine)

    # 2. Đảm bảo các cặp khóa nghiệp vụ đã sẵn sàng
    _ = key_manager.rsa_public_numbers
    _ = key_manager.ec_public_key_hex

    # 3. Tạo sẵn các thư mục lưu trữ an toàn
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    (settings.uploads_path / "evidences").mkdir(parents=True, exist_ok=True)
    (settings.uploads_path / "docs").mkdir(parents=True, exist_ok=True)

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Nền tảng Mạng truyền thông nội bộ doanh nghiệp kết hợp Cổng tố giác sai phạm ẩn danh "
        "với cơ chế Ký mù RSA Chaum, Mã hóa bất đối xứng ECIES P-256 và Kênh Chat E2EE."
    ),
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Zero-Knowledge Sanitizer Middleware (Tẩy sạch Header IP cho Anonymous Routes)
@app.middleware("http")
async def sanitize_anonymous_request_middleware(request: Request, call_next):
    if request.url.path.startswith(f"{settings.API_V1_STR}/anonymous"):
        # Xóa bỏ các headers định danh có thể làm lộ địa chỉ IP hoặc thông tin thiết bị
        sensitive_headers = {b"x-forwarded-for", b"x-real-ip", b"client-ip"}
        cleaned_headers = [
            (key, val) for key, val in request.scope.get("headers", [])
            if key.lower() not in sensitive_headers
        ]
        request.scope["headers"] = cleaned_headers

    response = await call_next(request)
    return response


# 3. Mount Static Uploads (Tài liệu nội bộ & Bằng chứng mã hóa)
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_path)), name="uploads")

# 4. Include API Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth")
app.include_router(posts.router, prefix=f"{settings.API_V1_STR}/posts")
app.include_router(compliance.router, prefix=f"{settings.API_V1_STR}/compliance")
app.include_router(anonymous.router, prefix=f"{settings.API_V1_STR}/anonymous")
app.include_router(officer.router, prefix=f"{settings.API_V1_STR}/officer")
app.include_router(admin_web.router)


# 5. Root & Health Check Endpoints
@app.get("/health", tags=["System"])
def health_check():
    """Kiểm tra trạng thái hoạt động của hệ thống."""
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "api_version": "v1"
    }


@app.get("/", tags=["System"])
def root_redirect():
    """Chuyển hướng hoặc cung cấp thông tin chào mừng."""
    return {
        "message": "Hệ thống Secure Internal Comms & Whistleblower Engine đang hoạt động.",
        "documentation": "/docs"
    }
