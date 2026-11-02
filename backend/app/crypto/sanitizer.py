"""Metadata Sanitizer Module (ATBM).
Loại bỏ siêu dữ liệu nhạy cảm (EXIF, GPS, Device Info) từ các file ảnh và tài liệu
trước khi mã hóa và gửi lên máy chủ để bảo vệ tính ẩn danh của người tố cáo.
"""

import io
from PIL import Image


def strip_image_metadata(image_bytes: bytes, image_format: str = "JPEG") -> bytes:
    """Tẩy sạch toàn bộ EXIF, GPS và metadata nhúng trong ảnh.
    
    Tạo một ảnh mới chỉ chứa pixel thô (raw pixels) và xuất ra byte stream mà không
    kèm bất kỳ thẻ EXIF hay thông tin nhạy cảm nào.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Tạo ảnh mới từ raw bytes để lột sạch toàn bộ metadata/EXIF ở mức C-level
        mode = "RGB" if img.mode in ("RGBA", "P") else img.mode
        converted = img.convert("RGB") if img.mode in ("RGBA", "P") else img
        clean_img = Image.frombytes(mode, converted.size, converted.tobytes())
        
        output = io.BytesIO()
        clean_img.save(output, format=image_format)
        return output.getvalue()
