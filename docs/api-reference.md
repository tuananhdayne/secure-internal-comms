# Tài Liệu Đặc Tả Chi Tiết API (API Reference)
> **Dự án:** Secure Internal Communications & Whistleblower Engine (ATBM - KMA)  
> **Base URL:** `http://localhost:8000` (hoặc `http://10.0.2.2:8000` trên Android Emulator)  
> **Phiên bản:** v1.0.0  

---

## 1. Tổng Quan Cơ Chế Xác Thực & Phân Quyền

Hệ thống phân chia 2 nhóm endpoints rõ rệt:

1. **Nhóm Endpoints Định Danh (Cụm 1 & Quản trị):**
   - Yêu cầu Header: `Authorization: Bearer <JWT_ACCESS_TOKEN>`.
   - Phân quyền theo vai trò (`role`): `EMPLOYEE`, `COMPLIANCE_OFFICER`, `BOARD_OF_DIRECTORS`, `SYSTEM_ADMIN`.
2. **Nhóm Endpoints Ẩn Danh (Cụm 2 - Zero-Knowledge):**
   - Tuyệt đối **KHÔNG** yêu cầu Header `Authorization`.
   - Hệ thống tự động tẩy sạch các Header nhạy cảm (`X-Forwarded-For`, `Client-IP`) thông qua middleware `sanitize_anonymous_request_middleware`.
   - Xác thực quyền nộp hồ sơ dựa hoàn toàn trên tính đúng đắn của Chữ ký mù RSA David Chaum ($s^e \equiv H \pmod N$).

---

## 2. Nhóm API Định Danh & Xác Thực (Auth)

### 2.1. Đăng nhập hệ thống (OAuth2 Password Bearer)
- **URL:** `POST /api/v1/auth/login`
- **Content-Type:** `application/x-www-form-urlencoded`
- **Request Body:**
  | Field | Type | Description |
  |---|---|---|
  | `username` | string | Mã nhân viên (VD: `NV001`, `TT001`, `AD001`) |
  | `password` | string | Mật khẩu tài khoản (VD: `employee123`) |
- **Response `200 OK`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "EMPLOYEE"
}
```
- **Error Codes:** `400 Bad Request` (Mã nhân viên hoặc mật khẩu sai; Tài khoản bị khóa).

---

### 2.2. Lấy thông tin hồ sơ người dùng hiện tại
- **URL:** `GET /api/v1/auth/me`
- **Headers:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Response `200 OK`:**
```json
{
  "id": 1,
  "employee_code": "NV001",
  "full_name": "Nguyễn Văn An",
  "department": "Nghiên cứu & Phát triển (R&D)",
  "role": "EMPLOYEE",
  "is_active": true,
  "created_at": "2026-11-01T15:00:00Z"
}
```

---

## 3. Nhóm API Truyền Thông & Bảng Tin Nội Bộ (Posts)

### 3.1. Danh sách bài viết thông báo
- **URL:** `GET /api/v1/posts`
- **Headers:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Query Params:** `skip=0`, `limit=20`, `category=GENERAL` (tùy chọn)
- **Response `200 OK`:**
```json
[
  {
    "id": 1,
    "title": "Chính sách Bảo mật Thông tin và Quy định Sử dụng Thiết bị Di động",
    "content": "Toàn thể cán bộ nhân viên tuân thủ nghiêm ngặt quy định an toàn thông tin...",
    "category": "SECURITY",
    "is_pinned": true,
    "author_id": 3,
    "author_name": "Nguyễn Quản Trị",
    "created_at": "2026-11-01T08:00:00Z",
    "comments": [
      {
        "id": 1,
        "author_name": "Nguyễn Văn An",
        "content": "Đã tiếp nhận và cam kết tuân thủ quy định.",
        "created_at": "2026-11-01T09:30:00Z"
      }
    ]
  }
]
```

### 3.2. Bình luận bài viết nội bộ
- **URL:** `POST /api/v1/posts/{post_id}/comments`
- **Headers:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Request Body (JSON):**
```json
{
  "content": "Phòng R&D hoàn toàn nhất trí với thông báo này."
}
```
- **Response `201 Created`**

---

## 4. Nhóm API Cấp Phát Chữ Ký Mù (Compliance)

### 4.1. Công khai cặp khóa công khai của Ban Thanh Tra
- **URL:** `GET /api/v1/compliance/public-keys`
- **Headers:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Response `200 OK`:**
```json
{
  "blind_sign_pub": {
    "e": "0x10001",
    "n": "0xc14f9d..."
  },
  "chat_pub_hex": "04a1b2c3..."
}
```
*(Trong đó `blind_sign_pub` là RSA-2048 Public Key dùng để làm mù; `chat_pub_hex` là ECC SECP256R1 Public Key dùng để mã hóa ECIES).*

### 4.2. Yêu cầu Ban Thanh Tra ký mù (Kiểm soát Quota)
- **URL:** `POST /api/v1/compliance/blind-sign`
- **Headers:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`
- **Request Body (JSON):**
```json
{
  "blinded_hash": "9455eb0b9219eca6..."
}
```
- **Response `200 OK`:**
```json
{
  "blind_signature": "7a8b9c0d1e2f..."
}
```
*(Lưu ý: Bảng hạn mức chỉ ghi nhận số lượt yêu cầu `request_count`, tuyệt đối không ghi thời gian để bảo đảm tính Unlinkability).*

---

## 5. Nhóm API Tố Giác Sai Phạm Ẩn Danh (Zero-Knowledge)

### 5.1. Nộp hồ sơ sai phạm ẩn danh
- **URL:** `POST /api/v1/anonymous/cases`
- **Headers:** *KHÔNG GỬI Authorization Header*
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  | Field | Type | Description |
  |---|---|---|
  | `category` | string | Danh mục sai phạm (Tham ô, Quấy rối, Vi phạm bảo mật) |
  | `encrypted_title` | string | Tiêu đề đã mã hóa ECIES |
  | `encrypted_description` | string | Mô tả chi tiết đã mã hóa ECIES |
  | `payload_ephemeral_pub` | string | Khóa EC tạm thời (65 bytes hex) |
  | `payload_iv` | string | Vector khởi tạo AES-GCM (12 bytes hex) |
  | `payload_auth_tag` | string | Thẻ xác thực AES-GCM (16 bytes hex) |
  | `case_token` | string | Mã định danh vụ việc do Client sinh (VD: `CASE-173047...`) |
  | `case_public_key` | string | Khóa công khai EC của vụ việc (dùng để chat E2EE) |
  | `unblinded_signature` | string | Chữ ký mù RSA sau khi bóc mù ($s$) |
  | `files` | binary[] | Danh sách tệp bằng chứng đã được mã hóa AES-GCM |
- **Response `201 Created`:**
```json
{
  "case_token": "CASE-1730472000000-E2E",
  "status": "PENDING",
  "message": "Hồ sơ tố giác ẩn danh đã được tiếp nhận an toàn."
}
```
- **Error Codes:** `400 Bad Request` (Chữ ký mù sai lệch; Mã băm bằng chứng hoặc nội dung bị tráo đổi).

### 5.2. Tra cứu trạng thái vụ việc & lịch sử tin nhắn
- **URL:** `GET /api/v1/anonymous/cases/{case_token}`
- **Headers:** *KHÔNG GỬI Authorization Header*
- **Response `200 OK`:**
```json
{
  "case_token": "CASE-1730472000000-E2E",
  "status": "UNDER_INVESTIGATION",
  "category": "Tham ô tài sản",
  "created_bucket": "2026-11-01T15:00:00Z",
  "messages": [
    {
      "id": 1,
      "sender_type": "COMPLIANCE_OFFICER",
      "ephemeral_pub_key": "04d4e5...",
      "nonce_iv": "112233...",
      "encrypted_message": "a8b9c0...",
      "auth_tag": "ffee00...",
      "digital_signature": "304502...",
      "created_at": "2026-11-01T15:20:00Z"
    }
  ]
}
```

### 5.3. Người tố cáo gửi tin nhắn bổ sung (Chat E2EE)
- **URL:** `POST /api/v1/anonymous/cases/{case_token}/messages`
- **Request Body (JSON):**
```json
{
  "ephemeral_pub_key": "041234...",
  "nonce_iv": "aabbcc...",
  "encrypted_message": "778899...",
  "auth_tag": "334455...",
  "digital_signature": "304402..."
}
```
*(Trường `digital_signature` bắt buộc phải là chữ ký số ECDSA được ký bằng `case_private_key` của vụ việc).*

---

## 6. Nhóm API Dành Cho Ban Thanh Tra (Officer)

### 6.1. Danh sách toàn bộ vụ việc
- **URL:** `GET /api/v1/officer/cases`
- **Headers:** `Authorization: Bearer <OFFICER_JWT_TOKEN>`
- **Response `200 OK`**

### 6.2. Giải mã chi tiết vụ việc
- **URL:** `GET /api/v1/officer/cases/{case_id}/decrypt`
- **Headers:** `Authorization: Bearer <OFFICER_JWT_TOKEN>`
- **Response `200 OK`:**
```json
{
  "id": 1,
  "case_token": "CASE-1730472000000-E2E",
  "category": "Tham ô tài sản",
  "status": "UNDER_INVESTIGATION",
  "decrypted_title": "Gian lận quỹ tài chính chi nhánh miền Bắc",
  "decrypted_description": "Phát hiện lập 2 sổ sách kế toán để trốn thuế...",
  "created_bucket": "2026-11-01T15:00:00Z",
  "evidences": [...],
  "messages": [...]
}
```

### 6.3. Cập nhật trạng thái xử lý
- **URL:** `PATCH /api/v1/officer/cases/{case_id}/status`
- **Request Body (JSON):** `{"status": "RESOLVED"}`

### 6.4. Gửi phản hồi điều tra tới người tố cáo
- **URL:** `POST /api/v1/officer/cases/{case_id}/reply`
- **Headers:** `Authorization: Bearer <OFFICER_JWT_TOKEN>`
- **Request Body (JSON):** Gói tin mã hóa ECIES bằng `case_public_key` của vụ việc.
