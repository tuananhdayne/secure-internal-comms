"""Lưu trữ tệp bằng chứng của hồ sơ ẩn danh.

Thứ tự xử lý cho mỗi tệp:
1. Đọc nội dung; bỏ qua tệp rỗng.
2. Nếu là ảnh còn EXIF -> tẩy metadata (phòng thủ chiều sâu; client đã tẩy trước khi băm).
3. Tính SHA-256 (giá trị này tham gia vào mã băm H của chữ ký mù).
4. Chuẩn hóa tên tệp + MIME (dữ liệu không tin cậy, sẽ hiển thị lại trên trang Thanh tra).
5. Ghi ra `uploads/evidences/<uuid>_<tên-an-toàn>`.

Nếu bước xác minh chữ ký sau đó thất bại, route gọi `discard()` để xóa các tệp đã ghi.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from fastapi import UploadFile
from PIL import Image

from app.core.config import settings
from app.crypto.sanitizer import strip_image_metadata

logger = logging.getLogger(__name__)

_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_VALID_MIME = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$")
MAX_FILENAME_LEN = 80
MAX_MIME_LEN = 50  # khớp cột case_evidences.mime_type String(50)
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
DEFAULT_MIME = "application/octet-stream"


def sanitize_filename(raw: Optional[str]) -> str:
    """Giữ lại tên tệp gốc ở dạng an toàn: chỉ chữ/số ASCII, '.', '_', '-'."""
    base = os.path.basename((raw or "").replace("\\", "/"))
    base = _SAFE_FILENAME_CHARS.sub("_", base).strip("._") or "evidence.bin"
    if len(base) > MAX_FILENAME_LEN:
        stem, dot, ext = base.rpartition(".")
        ext = ext[:10] if dot else ""
        base = (stem if dot else base)[: MAX_FILENAME_LEN - len(ext) - 1] + (f".{ext}" if ext else "")
    return base


def sanitize_mime(raw: Optional[str]) -> str:
    mime = (raw or "").split(";", 1)[0].strip().lower()
    return mime if (len(mime) <= MAX_MIME_LEN and _VALID_MIME.match(mime)) else DEFAULT_MIME


def _looks_like_image(upload: UploadFile) -> bool:
    return bool(
        (upload.content_type and upload.content_type.startswith("image/"))
        or (upload.filename and upload.filename.lower().endswith(IMAGE_EXTENSIONS))
    )


def _strip_exif_if_present(content: bytes, filename: Optional[str]) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as img:
            exif = img.getexif()
            if not exif:
                return content
        fmt = "PNG" if (filename or "").lower().endswith(".png") else "JPEG"
        return strip_image_metadata(content, image_format=fmt)
    except Exception:
        # Không phải ảnh hợp lệ -> giữ nguyên byte gốc (hash vẫn khớp với client).
        return content


class EvidenceRejected(ValueError):
    """Tệp vi phạm giới hạn (quá lớn / quá nhiều). Route trả HTTP 413."""


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Đọc theo khối 1 MB, dừng ngay khi vượt giới hạn (không nạp cả tệp lớn vào RAM)."""
    chunks, total = [], 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise EvidenceRejected(f"Tệp bằng chứng vượt quá {settings.MAX_EVIDENCE_FILE_MB} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


@dataclass(frozen=True)
class StoredEvidence:
    path: Path
    file_url: str
    sha256: str
    mime_type: str


async def store_uploads(files: Iterable[UploadFile]) -> List[StoredEvidence]:
    """Lưu các tệp tải lên và trả về thông tin đã chuẩn hóa (theo thứ tự gửi lên)."""
    target_dir = settings.uploads_path / "evidences"
    target_dir.mkdir(parents=True, exist_ok=True)
    uploads = list(files)
    if len(uploads) > settings.MAX_EVIDENCE_FILES:
        raise EvidenceRejected(f"Tối đa {settings.MAX_EVIDENCE_FILES} tệp bằng chứng cho mỗi hồ sơ.")
    max_bytes = settings.MAX_EVIDENCE_FILE_MB * 1024 * 1024
    stored: List[StoredEvidence] = []
    try:
        for upload in uploads:
            content = await _read_limited(upload, max_bytes)
            if not content:
                continue
            if _looks_like_image(upload):
                content = _strip_exif_if_present(content, upload.filename)

            safe_name = f"{uuid.uuid4().hex}_{sanitize_filename(upload.filename)}"
            dest = target_dir / safe_name
            dest.write_bytes(content)
            stored.append(StoredEvidence(
                path=dest,
                file_url=f"/uploads/evidences/{safe_name}",
                sha256=hashlib.sha256(content).hexdigest(),
                mime_type=sanitize_mime(upload.content_type),
            ))
    except Exception:
        discard(stored)
        raise
    return stored


def discard(items: Iterable[StoredEvidence]) -> None:
    """Xóa các tệp đã ghi (dùng khi hồ sơ bị từ chối)."""
    for item in items:
        try:
            item.path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Không xóa được tệp bằng chứng tạm %s: %s", item.path.name, exc)
