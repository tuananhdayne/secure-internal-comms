"""Lưu trữ tệp bằng chứng của hồ sơ ẩn danh.

Thứ tự xử lý cho mỗi tệp:
1. Đọc nội dung; bỏ qua tệp rỗng.
2. Nếu là ảnh còn EXIF -> tẩy metadata (phòng thủ chiều sâu; client đã tẩy trước khi băm).
3. Tính SHA-256 (giá trị này tham gia vào mã băm H của chữ ký mù).
4. Chuẩn hóa tên tệp + MIME (dữ liệu không tin cậy, sẽ hiển thị lại trên trang Thanh tra).
5. MÃ HÓA khi lưu (envelope): File_Key AES-256-GCM ngẫu nhiên cho từng tệp, File_Key được bọc
   bằng ECIES tới khóa công khai Ban Thanh tra. Trên đĩa chỉ có `uploads/evidences/<uuid>.enc`
   (cả tên tệp gốc cũng được mã hóa). SHA-256 vẫn tính trên nội dung gốc nên ràng buộc chữ ký mù
   không đổi.
6. Không phục vụ tĩnh: chỉ Thanh tra tải qua route có kiểm tra quyền (`load_plaintext`).

Nếu bước xác minh chữ ký sau đó thất bại, route gọi `discard()` để xóa các tệp đã ghi.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from fastapi import UploadFile
from PIL import Image

from app.core.config import settings
from app.crypto.ecies import ecies_decrypt, ecies_encrypt
from app.crypto.key_manager import key_manager
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


# ---------------------------------------------------------------------------
# Mã hóa khi lưu (envelope encryption)
# ---------------------------------------------------------------------------
# Định dạng tệp .enc:  MAGIC | uint32 độ dài header | header JSON | ciphertext AES-GCM (kèm tag)
# header = {"k": <File_Key bọc ECIES: eph/iv/ct/tag hex>, "iv": <iv nội dung hex>,
#           "n": <tên tệp gốc mã hóa bằng File_Key, hex>, "niv": <iv của tên, hex>}
MAGIC = b"ATBMEV1\n"
ENCRYPTED_PREFIX = "enc:"            # giá trị case_evidences.file_url cho tệp đã mã hóa
LEGACY_PREFIX = "/uploads/evidences/"  # bản ghi cũ (tệp rõ) — vẫn đọc được qua route có quyền


def encrypt_blob(content: bytes, filename: str) -> bytes:
    file_key = AESGCM.generate_key(bit_length=256)
    aes = AESGCM(file_key)
    iv, niv = os.urandom(12), os.urandom(12)
    wrapped = ecies_encrypt(key_manager.ec_public_key_hex, file_key)
    header = json.dumps({
        "k": wrapped,
        "iv": iv.hex(),
        "n": aes.encrypt(niv, filename.encode("utf-8"), None).hex(),
        "niv": niv.hex(),
    }).encode("utf-8")
    return MAGIC + len(header).to_bytes(4, "big") + header + aes.encrypt(iv, content, MAGIC)


def decrypt_blob(blob: bytes) -> Tuple[bytes, str]:
    """Trả về (nội dung gốc, tên tệp gốc). Ném ValueError nếu sai định dạng / bị sửa đổi."""
    if not blob.startswith(MAGIC):
        raise ValueError("Không phải tệp bằng chứng đã mã hóa")
    pos = len(MAGIC)
    hlen = int.from_bytes(blob[pos:pos + 4], "big")
    header = json.loads(blob[pos + 4:pos + 4 + hlen])
    k = header["k"]
    file_key = ecies_decrypt(
        key_manager.ec_private_key,
        k["ephemeral_public_key"], k["iv"], k["ciphertext"], k["auth_tag"],
    )
    aes = AESGCM(file_key)
    name = aes.decrypt(bytes.fromhex(header["niv"]), bytes.fromhex(header["n"]), None).decode("utf-8")
    content = aes.decrypt(bytes.fromhex(header["iv"]), blob[pos + 4 + hlen:], MAGIC)
    return content, name


def evidence_path(file_url: str) -> Optional[Path]:
    """Đường dẫn trên đĩa từ giá trị file_url trong CSDL (chống path traversal)."""
    base = settings.uploads_path / "evidences"
    if file_url.startswith(ENCRYPTED_PREFIX):
        name = file_url[len(ENCRYPTED_PREFIX):]
    elif file_url.startswith(LEGACY_PREFIX):
        name = file_url[len(LEGACY_PREFIX):]
    else:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        return None
    return base / name


def read_name(file_url: str) -> str:
    """Tên tệp gốc để hiển thị (chỉ giải mã phần header, không giải mã nội dung)."""
    path = evidence_path(file_url)
    if path is None or not path.is_file():
        return "(tệp không khả dụng)"
    if not file_url.startswith(ENCRYPTED_PREFIX):
        return re.sub(r"^[0-9a-f]{32}_", "", path.name)
    try:
        with path.open("rb") as f:
            head = f.read(len(MAGIC) + 4)
            if not head.startswith(MAGIC):
                return "(tệp không khả dụng)"
            header = json.loads(f.read(int.from_bytes(head[len(MAGIC):], "big")))
        k = header["k"]
        file_key = ecies_decrypt(key_manager.ec_private_key, k["ephemeral_public_key"], k["iv"], k["ciphertext"], k["auth_tag"])
        return AESGCM(file_key).decrypt(bytes.fromhex(header["niv"]), bytes.fromhex(header["n"]), None).decode("utf-8")
    except Exception:
        return "(tệp không khả dụng)"


# Ứng dụng di động tự gửi một tệp giữ chỗ "evidence_<ms>.bin" khi người dùng không đính kèm gì
# (để ràng buộc chữ ký). Đánh dấu bằng MIME riêng để giao diện ẩn đi.
PLACEHOLDER_MIME = "application/x-atbm-placeholder"
_PLACEHOLDER_NAME = re.compile(r"^evidence_\d+\.bin$")


def is_placeholder(file_url: str, mime_type: str) -> bool:
    return mime_type == PLACEHOLDER_MIME or bool(re.search(r"(?:^|/)(?:[0-9a-f]{32}_)?evidence_\d+\.bin$", file_url or ""))


def load_plaintext(file_url: str) -> Tuple[bytes, str]:
    """Đọc tệp bằng chứng cho Thanh tra: giải mã nếu là tệp .enc, đọc thẳng nếu là bản ghi cũ."""
    path = evidence_path(file_url)
    if path is None or not path.is_file():
        raise FileNotFoundError(file_url)
    data = path.read_bytes()
    if file_url.startswith(ENCRYPTED_PREFIX):
        return decrypt_blob(data)
    return data, re.sub(r"^[0-9a-f]{32}_", "", path.name)


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

            original_name = sanitize_filename(upload.filename)
            mime = sanitize_mime(upload.content_type)
            if mime == DEFAULT_MIME and _PLACEHOLDER_NAME.match(original_name):
                mime = PLACEHOLDER_MIME
            storage_name = f"{uuid.uuid4().hex}.enc"
            dest = target_dir / storage_name
            dest.write_bytes(encrypt_blob(content, original_name))
            stored.append(StoredEvidence(
                path=dest,
                file_url=f"{ENCRYPTED_PREFIX}{storage_name}",
                sha256=hashlib.sha256(content).hexdigest(),
                mime_type=mime,
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


def evidence_response(file_url: str, mime_type: str, download: bool = False):
    """Response trả tệp đã giải mã cho Thanh tra (route đã kiểm tra quyền trước khi gọi).

    Nội dung là dữ liệu KHÔNG tin cậy do người tố giác gửi: luôn kèm CSP sandbox + nosniff,
    không cache; HTML/SVG/… luôn tải về (attachment) thay vì hiển thị.
    """
    from urllib.parse import quote
    from fastapi.responses import Response

    content, name = load_plaintext(file_url)
    mime = mime_type if mime_type and mime_type != PLACEHOLDER_MIME else DEFAULT_MIME
    inline_ok = mime.startswith(("image/", "audio/", "video/")) and "svg" not in mime
    disposition = "inline" if (inline_ok and not download) else "attachment"
    return Response(
        content=content,
        media_type=mime if inline_ok else DEFAULT_MIME,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(name)}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )
