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
        # Chuyển đổi hệ màu sang RGB nếu cần (tránh lỗi với RGBA/P khi lưu JPEG)
        if img.mode in ("RGBA", "P"):
            clean_img = img.convert("RGB")
        else:
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(list(img.getdata()))
        
        output = io.BytesIO()
        clean_img.save(output, format=image_format)
        return output.getvalue()
