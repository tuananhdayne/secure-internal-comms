# 🛡️ ATBM Security Suite: Secure Internal Communications & Whistleblower Engine

> **Đồ án An toàn Bảo mật Hệ thống Thông tin — Học viện Kỹ thuật Mật mã (KMA)**  
> Hệ thống Truyền thông Nội bộ Doanh nghiệp kết hợp Cổng Tố Giác Sai Phạm Ẩn Danh (Zero-Knowledge Whistleblower Engine) ứng dụng **Chữ ký mù RSA Chaum (RSA-2048)**, **Mã hóa lai ECIES (ECC P-256 + HKDF-SHA256 + AES-256-GCM)**, **Kênh Chat E2EE hai chiều**, **SQLCipher Vault** và **Cơ chế Tiêu hủy Khẩn cấp Panic PIN**.

---

## 🌟 Kiến Trúc Cốt Lõi (Dual-Cluster Zero-Knowledge Architecture)

Hệ thống được thiết kế tách biệt vật lý và logic thành **2 Cụm độc lập** nhằm đảm bảo tính **Không thể liên kết (Unlinkability)**:

1. **Cụm 1 — Định danh & Truyền thông Nội bộ (`Identified Cluster`):**
   * Xác thực JWT (HS256) và phân quyền RBAC đa tầng (`EMPLOYEE`, `BOARD_DIRECTOR`, `COMPLIANCE_OFFICER`, `SYSTEM_ADMIN`).
   * Bảng tin nội bộ & bình luận được bảo vệ bởi lớp phủ **Dynamic Watermark** (`EmployeeCode + Timestamp`) và cờ phần cứng **`FLAG_SECURE`** chống chụp/quay màn hình trái phép.
   * **Cơ chế Cấp phát Chữ ký mù (`Blind Sign Quota`):** Xác nhận tư cách nhân viên nội bộ và giới hạn chống spam (`5 lượt/tuần`), hoàn toàn **không lưu dấu thời gian (`timestamp`)** để triệt tiêu tấn công tương quan thời gian (*Timing Correlation Attack*).
2. **Cụm 2 — Cổng Tố giác Ẩn danh & Điều tra (`Anonymous Whistleblower Cluster`):**
   * **Không định danh:** Không yêu cầu JWT, Middleware tự động lột sạch toàn bộ Header IP (`X-Forwarded-For`, `X-Real-IP`, `Client-IP`), không tồn tại cột `user_id` hay khóa ngoại nối sang bảng `users`.
   * **Làm mờ thời gian (`Time Bucketing`):** Mọi thời điểm nộp hồ sơ được làm tròn về đầu giờ chẵn (`minute=0, second=0`).
   * **Tẩy sạch siêu dữ liệu (`EXIF/GPS Sanitizer`):** Mọi hình ảnh bằng chứng được tái tạo từ pixel thô ở cả Client và Server để xóa 100% tọa độ GPS và thông tin thiết bị.
   * **Mã hóa Đầu-Cuối (`ECIES P-256`):** Chỉ duy nhất **Ban Thanh tra (`COMPLIANCE_OFFICER`)** nắm giữ khóa riêng ECC P-256 mới có thể giải mã hồ sơ và trao đổi E2EE với người tố giác. Ngay cả **Quản trị viên hệ thống (`SYSTEM_ADMIN`)** hoặc DBA cũng không thể đọc được nội dung (`HTTP 403 Forbidden`).

---

## 📂 Cấu Trúc Thư Mục Dự Án

```text
atbm/
├── README.md                          # Tổng quan dự án & hướng dẫn khởi chạy
├── backend/                           # Phân hệ Máy chủ (FastAPI + SQLAlchemy + Cryptography)
│   ├── .env.example                   # Mẫu cấu hình môi trường
│   ├── requirements.txt               # Danh mục thư viện phụ thuộc Python
│   ├── run_security_tests.py          # Suite 5 kịch bản kiểm toán bảo mật cốt lõi KMA
│   ├── app/
│   │   ├── main.py                    # Điểm nhập FastAPI & Zero-Knowledge Middleware
│   │   ├── core/                      # Cấu hình (`config.py`) & JWT/Hashing (`security.py`)
│   │   ├── crypto/                    # Mật mã học: `blind_signature.py`, `ecies.py`, `key_manager.py`, `sanitizer.py`
│   │   ├── db/                        # Quản lý kết nối SQLite WAL (`session.py`) & dữ liệu mẫu (`seed.py`)
│   │   ├── models/                    # ORM tách biệt: Cụm 1 (`identified.py`) & Cụm 2 (`anonymous.py`)
│   │   ├── schemas/                   # Pydantic Validation Schemas
│   │   ├── api/                       # Điều phối: `deps.py`, `admin_web.py` (SSR) & `v1/` (REST API)
│   │   └── templates/                 # Giao diện Jinja2 cho Cổng Quản trị & Thanh tra
│   └── tests/                         # Hệ thống Kiểm thử Phân tầng
│       ├── whitebox/                  # Kiểm thử Hộp trắng (Unit, Branch Coverage, Crypto Math, ORM)
│       ├── blackbox/                  # Kiểm thử Hộp đen (API, EP, BVA, Decision Table RBAC, E2E)
│       └── performance/               # Kiểm thử Hiệu năng & Chịu tải đồng thời
├── android/                           # Phân hệ Máy khách Di động (Kotlin + Jetpack Compose + SQLCipher)
│   └── app/src/
│       ├── main/kotlin/com/atbm/app/  # Mã nguồn ứng dụng Android
│       └── test/java/com/atbm/app/    # Kiểm thử đơn vị mật mã (`CryptoUnitTest.kt`)
└── docs/                              # Tài liệu Kỹ thuật & Kế hoạch Kiểm thử
    ├── implementation_plan.md         # Kiến trúc tổng thể & Lộ trình triển khai
    ├── security-whitepaper.md         # Sách trắng Mật mã học & Mô hình mối đe dọa
    ├── api-reference.md               # Đặc tả giao thức REST API
    ├── whitebox_blackbox_test_plan.md # Kế hoạch kiểm thử Hộp trắng & Hộp đen
    ├── master_test_plan.md            # Kế hoạch nghiệm thu tổng thể 4 trụ cột
    ├── test_execution_report.md       # Báo cáo số liệu thực thi kiểm thử
    ├── developer-guide.md             # Hướng dẫn cài đặt cho lập trình viên
    ├── user-manual.md                 # Hướng dẫn sử dụng cho Nhân viên, Thanh tra & Admin
    └── demo-defense-guide.md          # Kịch bản thuyết trình bảo vệ đồ án
```

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh (Quick Start)

### 1. Khởi chạy Backend & Web Portal (`FastAPI`)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Nạp dữ liệu mẫu (Tài khoản mặc định & Bản tin nội bộ)
PYTHONPATH=. python -m app.db.seed

# Khởi động Server tại http://0.0.0.0:8000
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000
```
* **Cổng Quản trị & Thanh tra Web:** `http://localhost:8000/admin/login`
* **Swagger API Docs:** `http://localhost:8000/docs`

### 2. Tài khoản Mẫu Mặc Định

| Vai trò | Mã nhân sự | Mật khẩu | Quyền hạn chính |
| :--- | :---: | :---: | :--- |
| **Nhân viên (`EMPLOYEE`)** | `NV001` / `NV002` | `employee123` | Xem bản tin, bình luận, xin chữ ký mù & gửi tố giác ẩn danh trên Mobile |
| **Thanh tra (`COMPLIANCE_OFFICER`)** | `TT001` | `officer123` | Thụ lý, giải mã ECIES hồ sơ tố giác và phản hồi E2EE tại `/admin/cases` |
| **Quản trị viên (`SYSTEM_ADMIN`)** | `AD001` | `admin123` | Quản lý nhân sự (`/admin/users`) & truyền thông (`/admin/posts`); **bị chặn giải mã hồ sơ tố giác** |
| **Ban Giám đốc (`BOARD_DIRECTOR`)** | `GD001` | `director123` | Đăng tải chính sách và thông báo ghim trên bảng tin nội bộ |

### 3. Cài đặt & Chạy Ứng dụng Android (`Pixel_8` Emulator)
```bash
# Chuyển tiếp cổng 8000 từ máy ảo về máy chủ cục bộ
adb reverse tcp:8000 tcp:8000

# Build và cài đặt APK Debug lên thiết bị/máy ảo
cd android
./gradlew installDebug
adb shell am start -n com.atbm.app/.MainActivity
```

---

## 🧪 Kiểm Thử & Kiểm Toán An Ninh (Testing & Verification)

1. **Chạy toàn bộ 51 bài kiểm thử Hộp trắng & Hộp đen (`pytest`):**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/whitebox backend/tests/blackbox -v
   ```
2. **Chạy bộ 5 kịch bản Kiểm toán Bảo mật cốt lõi KMA:**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/python backend/run_security_tests.py
   ```
3. **Chạy kiểm thử đơn vị mật mã trên Android (`JUnit 4`):**
   ```bash
   cd android && ./gradlew testDebugUnitTest
   ```
4. **Chạy đo kiểm hiệu năng mật mã & chịu tải đồng thời:**
   ```bash
   PYTHONPATH=backend ./backend/.venv/bin/python backend/tests/performance/benchmark_crypto.py
   PYTHONPATH=backend ./backend/.venv/bin/python backend/tests/performance/load_test_concurrency.py
   ```
