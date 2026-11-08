# Kế Hoạch Triển Khai Chi Tiết & Bảng Theo Dõi Tiến Độ (Task Tracker)
> **Dự án:** Secure Internal Communications & Whistleblower Engine (ATBM - KMA)  
> **Tài liệu tham chiếu thiết kế:** [docs/implementation_plan.md](file:///home/tuananh/KMA/atbm/docs/implementation_plan.md)  
> **Nguyên tắc theo dõi:** Cập nhật trạng thái checkbox `[ ]` -> `[x]` ngay khi hoàn thành và verify từng task.  
> **Ràng buộc kỹ thuật:** Tuân thủ nghiêm ngặt 4 bộ quy chuẩn phát triển phần mềm (Bảo mật, Kỷ luật kiến trúc, Chuẩn viết mã, Kiểm thử).

---

## BẢNG TỔNG HỢP TIẾN ĐỘ DỰ ÁN

| Giai đoạn | Tổng số Task | Đã hoàn thành | Đang thực hiện | Còn lại | Tiến độ |
|-----------|--------------|---------------|----------------|---------|---------|
| **Nền tảng cốt lõi (Core Scaffolding)** | 4 | 4 | 0 | 0 | **100%** |
| **Giai đoạn 1: Backend Server & Security Engine** | 16 | 16 | 0 | 0 | **100%** |
| **Giai đoạn 2: Ứng dụng Android (Compose + Hardening)** | 6 | 6 | 0 | 0 | **100%** |
| **Giai đoạn 3: Tích hợp, Bộ tài liệu bàn giao & Nghiệm thu** | 3 | 3 | 0 | 0 | **100%** |
| **TỔNG CỘNG TOÀN DỰ ÁN** | **29** | **29** | **0** | **0** | **100%** |

---

## CÁC THÀNH PHẦN ĐÃ HOÀN THÀNH (CỐT LÕI MẬT MÃ & CẤU HÌNH)

- [x] **Task 0.1: Cấu hình hệ thống & Quản lý môi trường an toàn**
  - **File:** `backend/app/core/config.py`, `backend/.env.example`, `.gitignore`
  - **Kết quả:** Pydantic `Settings` quản lý đầy đủ JWT, Database, RSA/ECC Keys, Uploads, và Blind Sign Quota ($K=5$). Không commit thông tin nhạy cảm.
- [x] **Task 0.2: Bảo mật định danh & Băm mật khẩu**
  - **File:** `backend/app/core/security.py`
  - **Kết quả:** `get_password_hash` (bcrypt), `verify_password`, `create_access_token` (JWT HS256), `decode_access_token`.
- [x] **Task 0.3: Quản lý cặp khóa nghiệp vụ phân tách độc lập**
  - **File:** `backend/app/crypto/key_manager.py`
  - **Kết quả:** Tách biệt tuyệt đối `Officer_BlindSign_KeyPair` (RSA-2048) và `Officer_Chat_KeyPair` (ECC P-256). Tự động sinh và lưu trữ PEM an toàn.
- [x] **Task 0.4: Động cơ Ký mù RSA Chaum (Math Proof & Client Simulation)**
  - **File:** `backend/app/crypto/blind_signature.py`
  - **Kết quả:** `BlindSignatureEngine` thực thi:
    - Băm thông điệp $H \pmod N$
    - Làm mù $m^* = (H \cdot r^e) \pmod N$
    - Ký mù $s^* = (m^*)^d \pmod N$
    - Bóc mù $s = (s^* \cdot r^{-1}) \pmod N$
    - Xác minh $s^e \equiv H \pmod N$

---

## GIAI ĐOẠN 1: BACKEND SERVER & SECURITY ENGINE (16 TASKS)

### [x] Task 1: Module Mã hóa Bất đối xứng ECIES (`crypto/ecies.py`)
- **Mục tiêu:** Mã hóa Title, Description, File_Key của hồ sơ tố cáo và tin nhắn chat 2 chiều E2EE.
- **Files:**
  - Tạo mới: `backend/app/crypto/ecies.py`
  - Test: `backend/tests/test_ecies.py`
- **Interfaces:**
  - Consumes: `Officer_Chat_KeyPair` từ `key_manager.py`
  - Produces:
    - `ecies_encrypt(recipient_pub_hex: str, plaintext: bytes) -> dict[str, str]` (trả về `ephemeral_pub`, `iv`, `ciphertext`, `tag`)
    - `ecies_decrypt(recipient_priv_key, ephemeral_pub_hex: str, iv_hex: str, ciphertext_hex: str, tag_hex: str) -> bytes`
- [x] **Step 1.1:** Viết failing unit test trong `backend/tests/test_ecies.py` (Roundtrip Encrypt/Decrypt, Test giải mã sai khóa bị quăng lỗi).
- [x] **Step 1.2:** Chạy test xác nhận FAIL: `pytest backend/tests/test_ecies.py -v`
- [x] **Step 1.3:** Triển khai thuật toán ECDH (P-256) + HKDF-SHA256 (sinh 32 bytes AES key) + AES-256-GCM trong `crypto/ecies.py`.
- [x] **Step 1.4:** Chạy test xác nhận PASS: `pytest backend/tests/test_ecies.py -v` (4/4 tests passed)

---

### [x] Task 2: Package Initialization & Module Exports
- **Mục tiêu:** Khởi tạo các gói Python package chuẩn mực, tránh circular import.
- **Files:**
  - Tạo mới: `backend/app/__init__.py`, `backend/app/models/__init__.py`, `backend/app/schemas/__init__.py`, `backend/app/db/__init__.py`, `backend/app/api/__init__.py`, `backend/app/api/v1/__init__.py`, `backend/tests/__init__.py`
- [x] **Step 2.1:** Tạo các file `__init__.py` tương ứng.
- [x] **Step 2.2:** Verify import xuyên suốt: `python -c "import app.core, app.crypto, app.models, app.schemas, app.db, app.api, app.api.v1"`

---

### [x] Task 3: SQLAlchemy Database Session & Base Engine
- **Mục tiêu:** Cấu hình SQLite engine (`app.db`), SessionLocal scoped session, declarative Base.
- **Files:**
  - Tạo mới: `backend/app/db/session.py`
  - Test: `backend/tests/test_db_session.py`
- **Interfaces:**
  - Produces: `engine`, `SessionLocal`, `Base`
- [x] **Step 3.1:** Viết unit test kết nối và transaction rollback trong `tests/test_db_session.py`.
- [x] **Step 3.2:** Triển khai `backend/app/db/session.py` với cấu hình WAL mode và Foreign Key constraint cho SQLite.
- [x] **Step 3.3:** Chạy test xác nhận PASS (3/3 tests passed).

---

### [x] Task 4: SQLAlchemy Models — Cụm 1: Quản trị & Định danh
- **Mục tiêu:** Lưu trữ người dùng, bài viết nội bộ, quota ký mù (tuyệt đối không lưu correlation timestamp).
- **Files:**
  - Tạo mới: `backend/app/models/identified.py`
  - Test: `backend/tests/test_identified_models.py`
- **Tables:**
  - `users`: `id`, `employee_code` (unique), `password_hash`, `full_name`, `department`, `role` (EMPLOYEE, COMPLIANCE_OFFICER, BOARD_DIRECTOR, SYSTEM_ADMIN), `is_active`, `created_at`
  - `blind_sign_quotas`: `id`, `user_id` (FK users.id, unique per week_epoch), `week_epoch`, `request_count` (Max $K=5$). **NGHIÊM CẤM có trường `last_requested_at`**.
  - `posts`: `id`, `author_id` (FK users.id), `title`, `content`, `category`, `attachment_url`, `is_pinned`, `created_at`
  - `comments`: `id`, `post_id` (FK posts.id), `author_id` (FK users.id), `content`, `created_at`
- [x] **Step 4.1:** Viết test kiểm tra cấu trúc bảng và assert không tồn tại cột timestamp trong bảng `blind_sign_quotas`.
- [x] **Step 4.2:** Triển khai `backend/app/models/identified.py`.
- [x] **Step 4.3:** Chạy `pytest backend/tests/test_identified_models.py -v` xác nhận PASS (3/3 tests passed).

---

### [x] Task 5: SQLAlchemy Models — Cụm 2: Tố giác Ẩn danh (Zero-Knowledge)
- **Mục tiêu:** Lưu trữ hồ sơ tố giác và tin nhắn chat E2EE. Tuyệt đối không có bất kỳ foreign key hay thông tin định danh nào sang Cụm 1.
- **Files:**
  - Tạo mới: `backend/app/models/anonymous.py`
  - Test: `backend/tests/test_anonymous_models.py`
- **Tables:**
  - `whistle_cases`:
    - `id` (INTEGER PK)
    - `case_token` (VARCHAR 64, UNIQUE, UUIDv4)
    - `category` (VARCHAR 50)
    - `encrypted_title` (TEXT)
    - `encrypted_description` (TEXT)
    - `payload_ephemeral_pub` (VARCHAR 130)
    - `payload_iv` (VARCHAR 32)
    - `payload_auth_tag` (VARCHAR 32)
    - `unblinded_signature` (TEXT)
    - `case_public_key` (TEXT - ECC P-256 Hex)
    - `status` (PENDING, INVESTIGATING, RESOLVED, REJECTED)
    - `created_bucket` (TIMESTAMP - làm tròn giờ, e.g., 2026-11-01 14:00:00)
  - `case_evidences`:
    - `id` (INTEGER PK), `case_id` (FK whistle_cases.id), `file_url` (TEXT), `file_sha256_hash` (VARCHAR 64), `mime_type` (VARCHAR 50)
  - `case_messages`:
    - `id` (INTEGER PK), `case_id` (FK whistle_cases.id), `sender_type` (ANONYMOUS_WHISTLEBLOWER, COMPLIANCE_OFFICER), `ephemeral_pub_key` (VARCHAR 130), `nonce_iv` (VARCHAR 32), `encrypted_message` (TEXT), `auth_tag` (VARCHAR 32), `digital_signature` (TEXT), `created_at`
- [x] **Step 5.1:** Viết test kiểm tra toàn vẹn schema Cụm 2: quét mọi cột của mọi bảng, assert không có `user_id`, `employee_code`, `ip_address`.
- [x] **Step 5.2:** Triển khai `backend/app/models/anonymous.py`.
- [x] **Step 5.3:** Chạy test xác nhận PASS (2/2 tests passed).

---

### [x] Task 6: Pydantic DTO Schemas
- **Mục tiêu:** Định nghĩa chuẩn dữ liệu đầu vào/ra cho toàn bộ API, bắt buộc đầy đủ Type Hints.
- **Files:**
  - `backend/app/schemas/auth.py`: `LoginRequest`, `TokenResponse`, `UserResponse`
  - `backend/app/schemas/posts.py`: `PostCreate`, `PostResponse`, `CommentCreate`, `CommentResponse`
  - `backend/app/schemas/compliance.py`: `BlindSignRequest`, `BlindSignResponse`, `OfficerKeysResponse`
  - `backend/app/schemas/anonymous.py`: `CaseCreateRequest`, `CaseResponse`, `MessageCreateRequest`, `MessageResponse`
  - `backend/app/schemas/officer.py`: `CaseStatusUpdate`, `OfficerReplyRequest`
- [x] **Step 6.1:** Viết test validate dữ liệu Pydantic (input hợp lệ / không hợp lệ).
- [x] **Step 6.2:** Triển khai toàn bộ file schemas trong `backend/app/schemas/`.
- [x] **Step 6.3:** Chạy test xác nhận PASS (4/4 tests passed).

---

### [x] Task 7: Dependency Injection & RBAC Middleware (`api/deps.py`)
- **Mục tiêu:** Cung cấp session DB (`get_db`), xác thực JWT (`get_current_user`), và phân quyền vai trò (`require_role`).
- **Files:**
  - Tạo mới: `backend/app/api/deps.py`
  - Test: `backend/tests/test_deps.py`
- [x] **Step 7.1:** Viết test: Token hợp lệ -> trả về user; Token hết hạn/sai -> 401; Role không đủ -> 403.
- [x] **Step 7.2:** Triển khai `get_db`, `get_current_user`, `require_role(["COMPLIANCE_OFFICER", ...])`.
- [x] **Step 7.3:** Chạy test xác nhận PASS (3/3 tests passed).

---

### [x] Task 8: Authentication API (`api/v1/auth.py`)
- **Mục tiêu:** Đăng nhập bằng `employee_code` + `password`, trả về JWT Token chứa `user_id`, `role`, `department`.
- **Files:**
  - Tạo mới: `backend/app/api/v1/auth.py`
  - Test: `backend/tests/test_auth_api.py`
- **Endpoints:**
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
- [x] **Step 8.1:** Viết test endpoint login (thành công, sai mật khẩu, tài khoản bị khóa).
- [x] **Step 8.2:** Triển khai `api/v1/auth.py`.
- [x] **Step 8.3:** Chạy test xác nhận PASS (3/3 tests passed).

---

### [x] Task 9: Seed Data Script (`db/seed.py`)
- **Mục tiêu:** Khởi tạo tài khoản mẫu và bài viết demo sẵn sàng kiểm thử và thuyết minh đồ án.
- **Files:**
  - Tạo mới: `backend/app/db/seed.py`
- **Dữ liệu seed:**
  - `NV001` (Nguyễn Văn An - R&D - EMPLOYEE)
  - `NV002` (Trần Thị Bình - Finance - EMPLOYEE)
  - `TT001` (Lê Thanh Tra - Internal Audit - COMPLIANCE_OFFICER)
  - `GD001` (Phạm Giám Đốc - Board - BOARD_DIRECTOR)
  - `AD001` (Hoàng Admin - IT Sec - SYSTEM_ADMIN)
  - 3 bài viết nội bộ mẫu (Chính sách bảo mật, Thông báo nghỉ lễ, Khảo sát môi trường làm việc).
- [x] **Step 9.1:** Triển khai script `seed.py`.
- [x] **Step 9.2:** Chạy lệnh `python -m app.db.seed` và kiểm tra DB có đủ 5 users và bài viết (PASS).

---

### [x] Task 10: Posts & Comments API (`api/v1/posts.py`)
- **Mục tiêu:** API Mạng truyền thông nội bộ có phân quyền RBAC.
- **Files:**
  - Tạo mới: `backend/app/api/v1/posts.py`
  - Test: `backend/tests/test_posts_api.py`
- **Endpoints:**
  - `GET /api/v1/posts`: Xem danh sách bài viết (EMPLOYEE+).
  - `POST /api/v1/posts`: Đăng bài mới (BOARD_DIRECTOR / SYSTEM_ADMIN).
  - `GET /api/v1/posts/{id}`: Xem chi tiết bài viết.
  - `POST /api/v1/posts/{id}/comments`: Thêm bình luận (EMPLOYEE+).
- [x] **Step 10.1:** Viết test quyền đăng bài (EMPLOYEE đăng bài -> 403, ADMIN đăng bài -> 201).
- [x] **Step 10.2:** Triển khai `api/v1/posts.py`.
- [x] **Step 10.3:** Chạy test xác nhận PASS (2/2 tests passed).

---

### [x] Task 11: Compliance API — Public Keys & Blind Sign (`api/v1/compliance.py`)
- **Mục tiêu:** Cấp phát chữ ký mù cho nhân viên hợp lệ kèm kiểm soát Quota tuần, tuyệt đối không lưu correlation timestamp.
- **Files:**
  - Tạo mới: `backend/app/api/v1/compliance.py`
  - Test: `backend/tests/test_compliance_api.py`
- **Endpoints:**
  - `GET /api/v1/compliance/public-keys`: Công khai `blind_sign_pub` $(e, N)$ và `chat_pub` (ECC Hex).
  - `POST /api/v1/compliance/blind-sign`: Yêu cầu JWT (Role EMPLOYEE). Kiểm tra Quota tuần $\le 5$. Ký mù $s^* \equiv (m^*)^d \pmod N$. Tăng `request_count`. Không log timestamp.
- [x] **Step 11.1:** Viết test: Ký mù trong hạn mức -> Thành công; Quá hạn mức lần thứ 6 -> 429 Too Many Requests; Kiểm tra DB `blind_sign_quotas` không có giờ phút giây.
- [x] **Step 11.2:** Triển khai `api/v1/compliance.py`.
- [x] **Step 11.3:** Chạy test xác nhận PASS (2/2 tests passed).

---

### [x] Task 12: Anonymous Submission & E2EE Chat API (`api/v1/anonymous.py`)
- **Mục tiêu:** Cổng nộp hồ sơ ẩn danh và chat 2 chiều. Không yêu cầu JWT, tắt log IP, xác minh tính toàn vẹn chữ ký mù.
- **Files:**
  - Tạo mới: `backend/app/api/v1/anonymous.py`
  - Test: `backend/tests/test_anonymous_api.py`
- **Endpoints:**
  - `POST /api/v1/anonymous/cases`:
    - Nhận: multipart/form-data: `category`, `encrypted_title`, `encrypted_description`, `payload_ephemeral_pub`, `payload_iv`, `payload_auth_tag`, `case_token`, `case_public_key`, `unblinded_signature`, `files[]` (đã được mã hóa AES-GCM).
    - Server tính mã băm toàn vẹn:
      $$H = \text{SHA256}(\text{Category} \parallel \text{Title} \parallel \text{Description} \parallel \text{Case\_Token} \parallel pk_{case} \parallel \text{SHA256}(F_1) \parallel \dots) \pmod N$$
    - Xác minh chữ ký mù: $s^e \equiv H \pmod N$. Nếu sai -> 400 Bad Request.
    - Ghi nhận `created_bucket` làm tròn giờ.
  - `GET /api/v1/anonymous/cases/{case_token}`: Xem trạng thái và lịch sử tin nhắn.
  - `POST /api/v1/anonymous/cases/{case_token}/messages`: Người tố cáo gửi tin nhắn (kèm chữ ký số ECDSA từ `case_private_key` để chống can thiệp).
- [x] **Step 12.1:** Viết test nộp hồ sơ hợp lệ -> 201; Nộp chữ ký sai -> 400; Tráo đổi file hoặc nội dung -> 400.
- [x] **Step 12.2:** Triển khai `api/v1/anonymous.py` kèm middleware xóa header `X-Forwarded-For` và tắt access log.
- [x] **Step 12.3:** Chạy test xác nhận PASS (3/3 tests passed).

---

### [x] Task 13: Officer Case Management & Investigation API (`api/v1/officer.py`)
- **Mục tiêu:** Dành riêng cho Ban Thanh tra (Role: COMPLIANCE_OFFICER) tiếp nhận, giải mã hồ sơ và phản hồi điều tra.
- **Files:**
  - Tạo mới: `backend/app/api/v1/officer.py`
  - Test: `backend/tests/test_officer_api.py`
- **Endpoints:**
  - `GET /api/v1/officer/cases`: Danh sách toàn bộ vụ việc.
  - `GET /api/v1/officer/cases/{case_id}/decrypt`: Dùng `Officer_Chat_PrivateKey` giải mã Title, Description, File_Key.
  - `PATCH /api/v1/officer/cases/{case_id}/status`: Cập nhật trạng thái xử lý.
  - `POST /api/v1/officer/cases/{case_id}/messages`: Gửi tin nhắn mã hóa ECIES tới người tố cáo (sử dụng `case_public_key`).
- [x] **Step 13.1:** Viết test quyền truy cập (EMPLOYEE truy cập -> 403, OFFICER truy cập -> 200). Test giải mã đúng nội dung ban đầu.
- [x] **Step 13.2:** Triển khai `api/v1/officer.py`.
- [x] **Step 13.3:** Chạy test xác nhận PASS (3/3 tests passed).

---

### [x] Task 14: FastAPI Main Application & CORS / Static Mounting
- **Mục tiêu:** Tích hợp toàn bộ router, xử lý lifecycle startup (tạo bảng, load keys), mount static uploads, chuẩn hóa OpenAPI docs.
- **Files:**
  - Tạo mới: `backend/app/main.py`
  - Test: `backend/tests/test_main.py`
- [x] **Step 14.1:** Viết test khởi động app và truy cập `/docs` trả về status 200.
- [x] **Step 14.2:** Triển khai `backend/app/main.py`.
- [x] **Step 14.3:** Chạy test xác nhận PASS (2/2 tests passed).

---

### [x] Task 15: Suite Tự Động Kiểm Thử 5 Kịch Bản Bảo Mật (`run_security_tests.py`)
- **Mục tiêu:** Tạo script độc lập chạy 5 bài test bảo mật cốt lõi, in output trực quan (Xanh/Đỏ) phục vụ hội đồng chấm đồ án.
- **Files:**
  - Tạo mới: `backend/run_security_tests.py`
- **5 Kịch bản bắt buộc:**
  1. **Chống chữ ký giả:** Giả lập người ngoài tự sinh chữ ký $s$ ngẫu nhiên -> API từ chối (PASS).
  2. **Chứng minh Unlinkability:** Quét CSDL Cụm 2 không tìm thấy bất kỳ liên kết nào tới Cụm 1; Bảng quota không lưu timestamp (PASS).
  3. **Chống tráo đổi bằng chứng:** Thay đổi 1 byte trong file hoặc description sau khi ký mù -> Server phát hiện sai lệch mã băm $H$ (PASS).
  4. **Tẩy sạch siêu dữ liệu (Metadata Sanitizer):** Ảnh chứa tọa độ GPS EXIF được làm sạch 100% (PASS).
  5. **Mô phỏng cơ chế Panic PIN:** Kích hoạt mã khẩn cấp -> Dữ liệu nhạy cảm bị tiêu hủy tức thì (PASS).
- [x] **Step 15.1:** Triển khai `backend/run_security_tests.py` và `backend/app/crypto/sanitizer.py`.
- [x] **Step 15.2:** Chạy lệnh `python backend/run_security_tests.py` và xác nhận 5/5 bài kiểm tra đều đạt ✅ (100% PASS).

---

### [x] Task 16: Giao diện Web Admin Quản Trị Hệ Thống (`admin_web.py` + Templates)
- **Mục tiêu:** Cung cấp giao diện web nhẹ nhàng (Jinja2 + HTML5/CSS) cho SYSTEM_ADMIN quản trị tài khoản và bài viết mà KHÔNG can thiệp được vào nội dung tố giác.
- **Files:**
  - `backend/app/api/admin_web.py`
  - `backend/app/templates/base.html`
  - `backend/app/templates/login.html`
  - `backend/app/templates/dashboard.html`
  - `backend/app/templates/users.html`
  - `backend/app/templates/posts.html`
  - Test: `backend/tests/test_admin_web.py`
- [x] **Step 16.1:** Triển khai router web admin và các file HTML templates (Giao diện Dark Navy/Slate sang trọng).
- [x] **Step 16.2:** Kiểm tra đăng nhập AD001, xem dashboard, quản lý nhân viên (khóa/mở khóa), tạo bài viết mới (4/4 tests passed).

---

## GIAI ĐOẠN 2: ỨNG DỤNG DI ĐỘNG ANDROID (6 TASKS)

### [x] Task 17: Khởi tạo Android Project & Gradle Scaffolding
- **Mục tiêu:** Thiết lập cấu trúc dự án Android Kotlin hiện đại, type-safe, cấu hình dependencies bảo mật.
- **Files:**
  - Thư mục: `android/`
  - Cấu hình: `build.gradle.kts`, `app/build.gradle.kts`, `gradle/libs.versions.toml`, `gradlew`
  - Dependencies: Jetpack Compose, Material 3, Retrofit + OkHttp, SQLCipher, Biometric, Security Crypto.
- [x] **Step 17.1:** Thiết lập cấu trúc thư mục và dependencies.
- [x] **Step 17.2:** Build project thành công bằng Gradle CLI: `./gradlew assembleDebug` (tạo `app-debug.apk` 34MB).

---

### [x] Task 18: Động cơ Mật mã học Di động (Pure BigInteger & Android JCA)
- **Mục tiêu:** Triển khai thuật toán chữ ký mù và ECIES trên Android không phụ thuộc BouncyCastle (tránh xung đột Android classloader).
- **Files:**
  - `android/app/src/main/kotlin/com/atbm/app/domain/crypto/RsaBlindClient.kt`: Blinding factor $r \in \mathbb{Z}_N^*$, $m^* = (H \cdot r^e) \pmod N$, $s = (s^* \cdot r^{-1}) \pmod N$.
  - `android/app/src/main/kotlin/com/atbm/app/domain/crypto/EciesHelper.kt`: Android JCA ECDH P-256 + HKDF-SHA256 + AES-256-GCM + ECDSA Sign.
  - `android/app/src/main/kotlin/com/atbm/app/domain/crypto/MetadataSanitizer.kt`: Xóa EXIF ảnh & GPS coordinates qua Bitmap re-compression, tính SHA-256.
  - Test: `android/app/src/test/java/com/atbm/app/domain/crypto/CryptoUnitTest.kt`
- [x] **Step 18.1:** Viết Android Unit Tests cho `RsaBlindClient` và `EciesHelper`.
- [x] **Step 18.2:** Chạy `./gradlew testDebugUnitTest` xác nhận PASS (100% tests passed).

---

### [x] Task 19: Local Secure Vault (SQLCipher) & Network Service Tách Biệt
- **Mục tiêu:** Lưu trữ cục bộ an toàn (`case_token`, `case_private_key`) và tạo 2 client Retrofit độc lập.
- **Files:**
  - `android/app/src/main/kotlin/com/atbm/app/data/db/SecureVaultDatabase.kt`: SQLite mã hóa bằng SQLCipher AES-256 kèm cơ chế Overwrite Shredding.
  - `android/app/src/main/kotlin/com/atbm/app/data/api/IdentifiedApi.kt`: Client đính kèm JWT Token.
  - `android/app/src/main/kotlin/com/atbm/app/data/api/AnonymousApi.kt`: Client Zero-Knowledge không đính kèm JWT/Cookie.
  - `android/app/src/main/kotlin/com/atbm/app/data/api/NetworkClient.kt`: Quản lý cấu hình Retrofit và IP Base URL động.
- [x] **Step 19.1:** Triển khai SecureVaultDatabase mã hóa SQLCipher và hàm `emergencyWipe()`.
- [x] **Step 19.2:** Hoàn thiện Retrofit Services cho Cụm 1 và Cụm 2.

---

### [x] Task 20: Android UI — Xác thực, Bảng tin & Dynamic Watermark
- **Mục tiêu:** Màn hình đăng nhập, đọc tin tức nội bộ và xem tài liệu kèm Watermark động chống chụp lén màn hình.
- **Files:**
  - `android/app/src/main/kotlin/com/atbm/app/ui/screens/LoginScreen.kt`: Đăng nhập bằng mã nhân viên và cấu hình URL Server.
  - `android/app/src/main/kotlin/com/atbm/app/ui/screens/NewsfeedScreen.kt`: Bảng tin nội bộ, đọc bài viết, xem bình luận.
  - `android/app/src/main/kotlin/com/atbm/app/ui/components/DynamicWatermark.kt`: Canvas vẽ Watermark chéo góc 45 độ đè thông tin định danh `Mã NV + Họ Tên + Timestamp` lên toàn bộ giao diện.
- [x] **Step 20.1:** Triển khai giao diện Jetpack Compose.
- [x] **Step 20.2:** Kiểm tra hiển thị watermark chính xác mã nhân viên hiện tại trên màn hình.

---

### [x] Task 21: Android UI — Luồng Tố Giác Ẩn Danh & Chat 2 Chiều E2EE
- **Mục tiêu:** Wizard nộp hồ sơ trực quan hóa các bước mật mã học và màn hình Chat điều tra ẩn danh.
- **Files:**
  - `android/app/src/main/kotlin/com/atbm/app/ui/screens/WhistleblowerScreen.kt`:
    - Bước 1: Nhập nội dung, phân loại danh mục sai phạm.
    - Bước 2: Tẩy sạch GPS/EXIF và mã hóa ECIES Title/Description.
    - Bước 3: Visualizer: Tạo $H \rightarrow$ Làm mù $m^* \rightarrow$ Ký mù RSA Chaum $\rightarrow$ Bóc mù $s \rightarrow$ Nộp ẩn danh.
  - `android/app/src/main/kotlin/com/atbm/app/ui/screens/VaultScreen.kt`: Danh sách các vụ việc đã nộp (truy xuất từ SQLCipher) và Chat điều tra 2 chiều E2EE.
- [x] **Step 21.1:** Triển khai các màn hình Compose Whistleblower & Vault.
- [x] **Step 21.2:** Kiểm thử gửi tin nhắn mã hóa và nhận phản hồi từ thanh tra viên.

---

### [x] Task 22: Bảo Vệ Ứng Dụng (Mobile Hardening) & Chế Độ Panic PIN
- **Mục tiêu:** Chống chụp ảnh màn hình và hủy dữ liệu nhạy cảm khẩn cấp khi người dùng bị ép buộc mở ứng dụng.
- **Files:**
  - `android/app/src/main/kotlin/com/atbm/app/MainActivity.kt`: Thiết lập `FLAG_SECURE` trên toàn bộ Window.
  - `android/app/src/main/kotlin/com/atbm/app/ui/screens/VaultScreen.kt`: Dialog kích hoạt Panic PIN (Mã khẩn cấp 999999).
- **Cơ chế:**
  - Cờ `FLAG_SECURE` chặn triệt để chụp ảnh màn hình, quay video màn hình và ẩn thumbnail trong Recent Apps.
  - Khi người dùng nhập `Panic PIN (999999)`: Ứng dụng lập tức thực thi Overwrite Shredding xóa sạch Database SQLCipher, xóa Private Keys, đưa ứng dụng về trạng thái trắng ngụy trang sạch sẽ.
- [x] **Step 22.1:** Kiểm tra cơ chế Panic PIN xóa sạch dữ liệu.
- [x] **Step 22.2:** Tích hợp `FLAG_SECURE` và hoàn tất build APK debug thành công.

---

## GIAI ĐOẠN 3: TÍCH HỢP, BỘ TÀI LIỆU BÀN GIAO & NGHIỆM THU (3 TASKS)

### [x] Task 23: Tích hợp End-to-End & Kiểm thử Liên thông
- **Mục tiêu:** Kết nối Android App (trên Emulator hoặc thiết bị thật qua LAN) tới FastAPI Backend, chạy trơn tru 5 kịch bản demo.
- **Files:**
  - Test: `backend/tests/test_e2e_integration.py`
- [x] **Step 23.1:** Cấu hình Base URL kết nối Backend LAN/Emulator linh hoạt qua `NetworkClient.updateBaseUrl`.
- [x] **Step 23.2:** Chạy trọn vẹn luồng liên thông End-to-End: Đăng nhập -> Lấy chữ ký mù -> Nộp hồ sơ -> Backend xác minh -> Web Admin/Officer xem & trả lời -> Mobile nhận phản hồi E2EE (`test_complete_end_to_end_flow` PASSED 100%).

---

### [x] Task 24: Bộ Tài Liệu Bàn Giao Hoàn Chỉnh Cho Dev & Người Dùng (6 Tài liệu)
- **Mục tiêu:** Cung cấp bộ tài liệu hoàn chỉnh bàn giao sản phẩm cho Developer, Người dùng cuối và Hội đồng chấm đồ án.
- **Tài liệu hoàn thiện trong thư mục `docs/`:**
  - [x] **24.1: `docs/developer-guide.md` (Dành cho Developer)**:
    - Hướng dẫn cài đặt môi trường (Python 3.12+, Android SDK/Studio).
    - Các bước chạy Backend và Android từ con số 0 trong 15 phút.
    - Cấu trúc thư mục, quy ước đặt tên và quy trình chạy tests.
  - [x] **24.2: `docs/api-reference.md` (Tài liệu API)**:
    - Đặc tả chi tiết toàn bộ 12 RESTful endpoints, request/response mẫu, mã lỗi, cơ chế auth.
  - [x] **24.3: `docs/security-whitepaper.md` (Giải trình Mật mã học - KMA)**:
    - Phân tích toán học cơ chế Blind Signature (Chaum).
    - Phân tích mô hình đe dọa (Threat Model) và chứng minh Unlinkability.
    - Cơ chế mã hóa E2EE và phòng chống rò rỉ siêu dữ liệu.
  - [x] **24.4: `docs/user-manual.md` (Dành cho Người dùng cuối)**:
    - Hướng dẫn cho Nhân viên (Đọc tin tức, xem PDF có watermark, gửi tố giác ẩn danh, cơ chế Panic PIN).
    - Hướng dẫn cho Ban Thanh tra (Tiếp nhận hồ sơ, giải mã điều tra, phản hồi ẩn danh).
    - Hướng dẫn cho Quản trị viên (Quản lý nhân viên, đăng bài viết).
  - [x] **24.5: `docs/demo-defense-guide.md` (Dành cho Buổi bảo vệ Đồ án)**:
    - Kịch bản demo 5 bài test bảo mật từng bước trước Hội đồng.
    - Bộ 12 câu hỏi phản biện chuyên sâu dự kiến và câu trả lời gợi ý chi tiết.
  - [x] **24.6: Cập nhật liên tục `docs/detailed_tasks.md`**:
    - Duy trì bảng checklist này làm tài liệu nghiệm thu tiến độ bàn giao (Đạt 100%).

---

### [x] Task 25: Đánh Giá An Toàn Cuối Cùng & Đóng Gói Phiên Bản (Release v1.0.0)
- **Mục tiêu:** Rà soát toàn bộ dự án, chạy test suite, kiểm tra rò rỉ bí mật và tạo Git Release Tag.
- [x] **Step 25.1:** Chạy lại `python backend/run_security_tests.py` đảm bảo 5/5 kịch bản xanh (413ms).
- [x] **Step 25.2:** Chạy lại toàn bộ `pytest backend/tests/` (40/40 tests PASSED) và Android Unit Tests & APK build (`testDebugUnitTest assembleDebug` PASSED).
- [x] **Step 25.3:** Kiểm tra `git status` đảm bảo không có file nhạy cảm lọt vào tracking (`.env`, `*.db`, keys, uploads).
- [x] **Step 25.4:** Đóng gói toàn bộ sản phẩm phiên bản `v1.0.0` sẵn sàng nghiệm thu và bảo vệ đồ án KMA.
