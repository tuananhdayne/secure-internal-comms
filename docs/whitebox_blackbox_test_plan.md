# Kế Hoạch Kiểm Thử Hộp Trắng (White-Box) & Hộp Đen (Black-Box) Toàn Diện

> **Dự án:** Secure Internal Communications & Whistleblower Engine (ATBM)  
> **Đơn vị:** Học viện Kỹ thuật Mật mã (KMA)  
> **Phạm vi:** Backend FastAPI (`backend/app`), Mobile Android (`android/app`), và Web Portal (`/admin`)  
> **Trạng thái:** Đã triển khai & Xác minh 100% PASS (51/51 Pytest + 5/5 KMA Security Suite + 3/3 Android JUnit)

---

## 1. Cấu Trúc Thư Mục Dự Án & Tổ Chức Kiểm Thử Đã Chuẩn Hóa

Toàn bộ dự án đã được dọn dẹp các tệp runtime trùng lặp ở thư mục gốc (`app.db*`, `keys/`, `uploads/` nay được cô lập hoàn toàn bên trong `backend/`) và tái cấu trúc thư mục kiểm thử theo đúng chuẩn phân tầng **Hộp trắng (White-Box)**, **Hộp đen (Black-Box)** và **Hiệu năng (Performance)**:

```text
atbm/
├── README.md                          # Tổng quan kiến trúc & hướng dẫn khởi chạy nhanh
├── backend/                           # Phân hệ Máy chủ (FastAPI + SQLAlchemy + Cryptography)
│   ├── .env.example                   # Mẫu cấu hình môi trường an toàn
│   ├── requirements.txt               # Danh mục thư viện phụ thuộc Python
│   ├── run_security_tests.py          # Suite 5 kịch bản kiểm toán bảo mật cốt lõi KMA
│   ├── app/
│   │   ├── main.py                    # Điểm nhập FastAPI, Lifespan & Zero-Knowledge Middleware
│   │   ├── core/                      # Cấu hình hệ thống (`config.py`) & JWT/Hashing (`security.py`)
│   │   ├── crypto/                    # Lõi mật mã: `blind_signature.py`, `ecies.py`, `key_manager.py`, `sanitizer.py`
│   │   ├── db/                        # Quản lý kết nối SQLite WAL (`session.py`) & dữ liệu mẫu (`seed.py`)
│   │   ├── models/                    # ORM tách biệt 2 cụm: Cụm 1 (`identified.py`) & Cụm 2 (`anonymous.py`)
│   │   ├── schemas/                   # Pydantic Validation Schemas
│   │   ├── api/                       # Tầng điều phối: `deps.py`, `admin_web.py` (SSR) & `v1/` (REST API)
│   │   └── templates/                 # Giao diện Jinja2 cho Cổng Quản trị & Thanh tra
│   └── tests/                         # Hệ thống Kiểm thử Phân tầng Chuẩn Hóa
│       ├── whitebox/                  # [HỘP TRẮNG] Kiểm thử cấu trúc nội bộ, nhánh lệnh, toán học mật mã & ORM
│       │   ├── test_crypto_whitebox.py
│       │   ├── test_ecies.py
│       │   ├── test_anonymous_models.py
│       │   ├── test_identified_models.py
│       │   ├── test_db_session.py
│       │   ├── test_deps.py
│       │   ├── test_schemas.py
│       │   └── test_seed.py
│       ├── blackbox/                  # [HỘP ĐEN] Kiểm thử chức năng API, Phân hoạch tương đương, Giá trị biên & RBAC
│       │   ├── test_boundary_and_equivalence.py
│       │   ├── test_auth_api.py
│       │   ├── test_posts_api.py
│       │   ├── test_compliance_api.py
│       │   ├── test_anonymous_api.py
│       │   ├── test_officer_api.py
│       │   ├── test_admin_web.py
│       │   ├── test_e2e_integration.py
│       │   └── test_main.py
│       └── performance/               # [HIỆU NĂNG & TẢI] Đo độ trễ mật mã & Chịu tải đồng thời
│           ├── benchmark_crypto.py
│           └── load_test_concurrency.py
├── android/                           # Phân hệ Máy khách Di động (Kotlin + Jetpack Compose + SQLCipher)
│   └── app/src/
│       ├── main/kotlin/com/atbm/app/  # Mã nguồn ứng dụng (UI, ViewModel, Repository, Crypto, SQLCipher)
│       └── test/java/com/atbm/app/    # [HỘP TRẮNG MOBILE] Kiểm thử đơn vị mật mã (`CryptoUnitTest.kt`)
└── docs/                              # Hệ thống Tài liệu Kỹ thuật & Nghiệm thu
    ├── implementation_plan.md         # Kiến trúc tổng thể & Lộ trình triển khai
    ├── detailed_tasks.md              # Đặc tả chi tiết từng task kỹ thuật
    ├── security-whitepaper.md         # Sách trắng Mật mã học & Mô hình mối đe dọa (Threat Model)
    ├── api-reference.md               # Đặc tả giao thức REST API
    ├── developer-guide.md             # Hướng dẫn cài đặt cho lập trình viên
    ├── user-manual.md                 # Hướng dẫn sử dụng cho Nhân viên, Thanh tra & Admin
    ├── whitebox_blackbox_test_plan.md # Kế hoạch kiểm thử Hộp trắng & Hộp đen (Tài liệu này)
    ├── master_test_plan.md            # Kế hoạch nghiệm thu tổng thể 4 trụ cột
    ├── test_execution_report.md       # Báo cáo số liệu thực thi kiểm thử
    └── demo-defense-guide.md          # Kịch bản thuyết trình bảo vệ đồ án 15 phút
```

---

## 2. Kế Hoạch Kiểm Thử Hộp Trắng (White-Box Testing Plan)

### 2.1. Phương pháp luận áp dụng
Kiểm thử hộp trắng tập trung vào **cấu trúc bên trong mã nguồn, luồng điều khiển (Control Flow), độ bao phủ nhánh (Branch/Decision Coverage), các bất biến toán học mật mã và ràng buộc cấu trúc CSDL**:
1. **Bao phủ câu lệnh & nhánh quyết định (Statement & Branch Coverage):** Đảm bảo mọi nhánh `if/else`, `try/except` trong các hàm mật mã (`blind_sign`, `verify`, `ecies_decrypt`, `strip_image_metadata`) và middleware phân quyền (`get_current_user`, `require_role`) đều được kích hoạt.
2. **Kiểm thử đường dẫn cơ sở (Basis Path Testing):** Kiểm tra các vòng lặp sắp xếp danh sách mã băm minh chứng `for file_hash in sorted(evidence_file_hashes)` và vòng lặp sinh số nguyên tố cùng nhau $\gcd(r, N) = 1$.
3. **Kiểm thử bất biến lược đồ CSDL (Schema & Constraint Introspection):** Dùng SQLAlchemy Inspector quét trực tiếp cấu trúc bảng ở mức metadata nội bộ để chứng minh Cụm 2 không có cột định danh và bảng `blind_sign_quotas` không có cột thời gian.

### 2.2. Ma trận Ca kiểm thử Hộp trắng (White-Box Test Cases)

| Mã TC | Tệp kiểm thử | Đối tượng bên trong (Internal Unit) | Kỹ thuật Hộp trắng | Nhánh / Điều kiện kiểm tra | Kết quả kỳ vọng |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **WB-01** | [`test_crypto_whitebox.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_crypto_whitebox.py) | `BlindSignatureEngine.blind_sign` | Branch Coverage | Nhánh `m_star <= 1` hoặc `m_star >= n` vs `1 < m_star < n` | Ném `ValueError` khi $m^* \in \{0, 1, -5, N, N+1\}$; trả về $s^* = (m^*)^d \bmod N$ khi hợp lệ |
| **WB-02** | [`test_crypto_whitebox.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_crypto_whitebox.py) | `BlindSignatureEngine.verify` | Branch Coverage | Nhánh `s <= 1` hoặc `s >= n` vs `pow(s, e, n) == h` | Trả về `False` ngay ở điều kiện biên $s \le 1 \lor s \ge N$; trả về `True` khi $s^e \bmod N == H$ |
| **WB-03** | [`test_crypto_whitebox.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_crypto_whitebox.py) | `compute_payload_hash` | Loop & Path Testing | Vòng lặp `sorted(evidence_file_hashes)` và độ nhạy 6 tham số đầu vào | Hoán vị thứ tự file không làm đổi $H$; thay đổi 1 ký tự bất kỳ làm đổi hoàn toàn $H$ |
| **WB-04** | [`test_crypto_whitebox.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_crypto_whitebox.py) | `strip_image_metadata` | Branch Coverage | Nhánh `img.mode in ("RGBA", "P")` vs `img.mode == "RGB"` có chứa EXIF GPS | Chuyển hệ màu RGBA sang RGB an toàn; `clean_img._getexif()` trả về `None` |
| **WB-05** | [`test_ecies.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_ecies.py) | `ecies_encrypt` / `ecies_decrypt` | Exception Path Coverage | Nhánh giải mã đúng khóa vs sai khóa riêng / sửa đổi `auth_tag` | Khôi phục đúng byte UTF-8 khi đúng khóa; ném `InvalidTag` khi sai khóa hoặc sửa tag |
| **WB-06** | [`test_anonymous_models.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_anonymous_models.py) | `WhistleCase`, `CaseEvidence`, `CaseMessage` | Schema Introspection | Quét `inspector.get_columns()` và `get_foreign_keys()` của Cụm 2 | Không tồn tại cột PII (`user_id`, `ip`); không có khóa ngoại nối sang bảng `users` |
| **WB-07** | [`test_identified_models.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_identified_models.py) | `BlindSignQuota`, `User`, `Post` | Schema Introspection | Quét cột bảng `blind_sign_quotas` chống Timing Correlation | Không có bất kỳ cột `created_at`, `updated_at`, `timestamp` nào trong `blind_sign_quotas` |
| **WB-08** | [`test_db_session.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_db_session.py) | `set_sqlite_pragma` & `get_db` | Event Hook Verification | Kiểm tra sự kiện `Engine.connect` thực thi `PRAGMA foreign_keys=ON` | Truy vấn `PRAGMA foreign_keys` trả về `1` |
| **WB-09** | [`test_deps.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_deps.py) | `get_current_user` & `require_role` | Decision Coverage | Token hợp lệ vs Token sai chữ ký JWT vs User không thuộc danh sách role | Trả về đối tượng `User` khi hợp lệ; ném `HTTPException(401)` hoặc `HTTPException(403)` |
| **WB-10** | [`test_schemas.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_schemas.py) & [`test_seed.py`](file:///home/tuananh/KMA/atbm/backend/tests/whitebox/test_seed.py) | Pydantic Models & `seed_database` | Idempotency & Type Validation | Kiểm tra khởi tạo schema và tính lũy đẳng khi gọi `seed_database()` nhiều lần | Dữ liệu mẫu khởi tạo đúng, không bị nhân bản khi chạy lại |
| **WB-11** | [`CryptoUnitTest.kt`](file:///home/tuananh/KMA/atbm/android/app/src/test/java/com/atbm/app/domain/crypto/CryptoUnitTest.kt) | Mobile `BlindSignatureManager`, `EciesManager` | Cross-Language Math Equivalence | Kiểm thử công thức toán học RSA-2048, ECIES P-256 và ECDSA trên JVM Kotlin | Tương thích 100% định dạng khóa X962 và HKDF info string `atbm-ecies-aes256gcm` với Backend |

---

## 3. Kế Hoạch Kiểm Thử Hộp Đen (Black-Box Testing Plan)

### 3.1. Phương pháp luận áp dụng
Kiểm thử hộp đen xem hệ thống như một khối đóng, chỉ tương tác qua giao diện HTTP REST API, Form Web SSR và giao diện người dùng dựa trên đặc tả yêu cầu:
1. **Phân hoạch tương đương (Equivalence Partitioning - EP):** Chia miền đầu vào thành các lớp Hợp lệ (Valid Partitions) và Không hợp lệ (Invalid Partitions) đối với thông tin đăng nhập, vai trò người dùng (`EMPLOYEE`, `COMPLIANCE_OFFICER`, `SYSTEM_ADMIN` vs `SUPER_HACKER`), và chữ ký mù.
2. **Phân tích giá trị biên (Boundary Value Analysis - BVA):** Kiểm tra ngay tại ranh giới hạn ngạch ký mù hàng tuần `WEEKLY_BLIND_SIGN_QUOTA = 5` với các giá trị biên: $1$ (biên dưới), $5$ (biên trên hợp lệ $\to$ HTTP 200), và $6$ (vượt biên trên $\to$ HTTP 429).
3. **Bảng quyết định (Decision Table Testing):** Kiểm tra ma trận phân quyền chéo (RBAC & Reverse RBAC) giữa `SYSTEM_ADMIN`, `COMPLIANCE_OFFICER`, `EMPLOYEE` và `ANONYMOUS` trên cả REST API lẫn cổng Web `/admin`.
4. **Kiểm thử chuyển đổi trạng thái (State Transition Testing):** Kiểm tra vòng đời trạng thái của hồ sơ tố giác (`RECEIVED` $\to$ `UNDER_INVESTIGATION` $\to$ `INVESTIGATING` $\to$ `RESOLVED` $\to$ `REJECTED`) và chặn các trạng thái nằm ngoài tập quy định.
5. **Kiểm thử đoán lỗi & tấn công (Error Guessing / Security Negative Testing):** Giả lập sửa đổi 1 byte minh chứng sau khi ký mù, chèn đường dẫn `../../../etc/` vào tên file upload, và gửi ảnh chứa tọa độ GPS EXIF.

### 3.2. Bảng Quyết Định Phân Quyền (Decision Table RBAC Matrix)

| Hành động / Endpoint | `ANONYMOUS` | `EMPLOYEE` | `COMPLIANCE_OFFICER` | `SYSTEM_ADMIN` |
| :--- | :---: | :---: | :---: | :---: |
| Xem bảng tin & Bình luận (`GET/POST /api/v1/posts`) | `401` | **Cho phép (`200/201`)** | **Cho phép (`200/201`)** | **Cho phép (`200/201`)** |
| Đăng bài viết mới (`POST /api/v1/posts`, `/admin/posts/create`) | `401` | `403 Forbidden` | **Cho phép** | **Cho phép** |
| Xin chữ ký mù (`POST /api/v1/compliance/blind-sign`) | `401` | **Cho phép ($\le 5$ lần/tuần)** | **Cho phép** | **Cho phép** |
| Nộp hồ sơ & Chat ẩn danh (`/api/v1/anonymous/cases`) | **Cho phép (Có chữ ký mù $s$)** | **Cho phép (Ẩn danh)** | **Cho phép (Ẩn danh)** | **Cho phép (Ẩn danh)** |
| Quản lý Nhân sự (`/admin/users/create`, `/toggle`) | `303 Login` | `303 Login` | **`403 Forbidden`** | **Cho phép (`303`)** |
| Thụ lý, Giải mã & Phản hồi Hồ sơ (`/admin/cases/*`, `/api/v1/officer/*`) | `401/303` | **`403 Forbidden`** | **Cho phép (`200/201`)** | **`403 Forbidden`** |

### 3.3. Ma trận Ca kiểm thử Hộp đen (Black-Box Test Cases)

| Mã TC | Kỹ thuật Hộp đen | Tệp kiểm thử | Đầu vào (Input) | Đầu ra kỳ vọng (Expected Output) |
| :--- | :--- | :--- | :--- | :--- |
| **BB-01** | Equivalence Partitioning (EP) | [`test_auth_api.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_auth_api.py) | (1) Đúng mã NV + mật khẩu; (2) Sai mật khẩu | (1) `200 OK` kèm JWT `access_token`; (2) `401 Unauthorized` |
| **BB-02** | Equivalence Partitioning (EP) | [`test_boundary_and_equivalence.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_boundary_and_equivalence.py) | Admin tạo user với `role="SUPER_HACKER"` (Phân hoạch không hợp lệ) | `400 Bad Request` (`Vai trò không hợp lệ`) |
| **BB-03** | Boundary Value Analysis (BVA) | [`test_boundary_and_equivalence.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_boundary_and_equivalence.py) | Nhân viên gọi `/api/v1/compliance/blind-sign` lần thứ `1..5` (trong biên) và lần thứ `6` (vượt biên) | Lần `1..5`: `200 OK` (`remaining_quota` giảm từ `4` về `0`); Lần `6`: `429 Too Many Requests` |
| **BB-04** | State Transition Testing | [`test_boundary_and_equivalence.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_boundary_and_equivalence.py) | Officer chuyển trạng thái hồ sơ qua các trạng thái hợp lệ và trạng thái lạ `"ARCHIVED_UNKNOWN"` | Hợp lệ: `200 OK`; Trạng thái lạ: `400 Bad Request` |
| **BB-05** | Error Guessing (Path Traversal) | [`test_boundary_and_equivalence.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_boundary_and_equivalence.py) | Upload file minh chứng có tên `../../../etc/traversal_test.bin` | `201 Created`; `file_url` được làm sạch thành `/uploads/evidences/<uuid>_traversal_test.bin` |
| **BB-06** | Decision Table (RBAC REST API) | [`test_officer_api.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_officer_api.py) | `EMPLOYEE` và `SYSTEM_ADMIN` gọi `/api/v1/officer/cases` và `/decrypt` | Cả 2 đều bị chặn với `403 Forbidden`; chỉ `COMPLIANCE_OFFICER` nhận `200 OK` |
| **BB-07** | Decision Table (Reverse RBAC Web) | [`test_admin_web.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_admin_web.py) | `SYSTEM_ADMIN` gọi `/admin/cases/{id}/decrypt`; `COMPLIANCE_OFFICER` gọi `/admin/users/create` | Cả 2 chiều vi phạm thẩm quyền chéo đều bị chặn với `403 Forbidden` |
| **BB-08** | Cryptographic Integrity (Tampering) | [`test_anonymous_api.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_anonymous_api.py) & [`run_security_tests.py`](file:///home/tuananh/KMA/atbm/backend/run_security_tests.py) | Sửa đổi 1 ký tự mô tả hoặc 1 byte file đính kèm sau khi đã xin chữ ký mù | `400 Bad Request` (`Chữ ký mù RSA không hợp lệ hoặc dữ liệu đã bị chỉnh sửa`) |
| **BB-09** | E2E Cross-Cluster Integration | [`test_e2e_integration.py`](file:///home/tuananh/KMA/atbm/backend/tests/blackbox/test_e2e_integration.py) | Luồng đầu-cuối: Login $\to$ Lấy khóa công khai $\to$ Ký mù $\to$ Nộp đơn ECIES $\to$ Officer giải mã $\to$ Phản hồi E2EE | Khôi phục đúng 100% tiêu đề/nội dung tiếng Việt; không lộ bản rõ trong `digital_signature` |

---

## 4. Hướng Dẫn Lệnh Thực Thi Kiểm Thử

1. **Chạy riêng bộ Kiểm thử Hộp trắng (White-Box Suite - 25 tests):**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/whitebox -v
   ```
2. **Chạy riêng bộ Kiểm thử Hộp đen (Black-Box Suite - 26 tests):**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/blackbox -v
   ```
3. **Chạy toàn bộ Pytest (White-Box + Black-Box = 51 tests):**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/whitebox backend/tests/blackbox -v
   ```
4. **Chạy bộ 5 Kịch bản Kiểm toán Bảo mật KMA:**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/python backend/run_security_tests.py
   ```
5. **Chạy bộ Kiểm thử Hiệu năng & Chịu tải (Performance & Load Suite):**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/python backend/tests/performance/benchmark_crypto.py
   PYTHONPATH=backend ./backend/.venv/bin/python backend/tests/performance/load_test_concurrency.py
   ```

