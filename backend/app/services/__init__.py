"""Tầng nghiệp vụ (services): logic dùng chung giữa REST API (`app/api/v1`) và Web Admin
(`app/api/admin_web.py`). Route chỉ nên lo HTTP (đọc request, kiểm quyền, trả response);
mọi xử lý mật mã / tệp / dữ liệu nằm ở đây để dễ đọc, dễ test và chỉ sửa một chỗ."""
