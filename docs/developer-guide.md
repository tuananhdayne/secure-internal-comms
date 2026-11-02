# Hướng Dẫn Kỹ Thuật Dành Cho Lập Trình Viên (Developer Guide)
> **Dự án:** Secure Internal Communications & Whistleblower Engine (ATBM)  
> **Đơn vị:** Học viện Kỹ thuật Mật mã (KMA) - Khóa Đồ án Chuyên ngành ATTT  
> **Phiên bản:** v1.0.0  

---

## 1. Giới Thiệu & Kiến Trúc Tổng Thể

Hệ thống **Secure Internal Communications & Whistleblower Engine** được thiết kế với kiến trúc **Zero-Knowledge Dual-Cluster** (CSDL 2 Cụm Phân Tách Tuyệt Đối), nhằm giải quyết bài toán mâu thuẫn giữa việc định danh nhân viên trong mạng truyền thông nội bộ và bảo đảm tính vô danh tuyệt đối khi tố giác sai phạm.

### Cấu trúc dự án:
```
atbm/
├── backend/                  # FastAPI Backend Server & Security Engine (Python 3.12+)
│   ├── app/
│   │   ├── api/             # Routers (v1: auth, posts, compliance, anonymous, officer; admin_web)
│   │   ├── core/            # Config (Pydantic Settings), Security (Bcrypt, JWT)
│   │   ├── crypto/          # Blind Signature (Chaum), ECIES (P-256), Key Manager, Metadata Sanitizer
│   │   ├── db/              # SessionLocal, Base, Seed script
│   │   ├── models/          # Cụm 1 (identified.py), Cụm 2 (anonymous.py)
│   │   ├── schemas/         # Pydantic Schemas có Type Hints
│   │   └── templates/       # Giao diện Jinja2 Admin Portal
│   ├── tests/               # Toàn bộ test suite Pytest (39+ unit tests & E2E)
│   ├── run_security_tests.py # Script kiểm thử 5 kịch bản bảo mật cốt lõi KMA
│   └── requirements.txt     # Danh sách thư viện Python
├── android/                  # Android Client (Kotlin, Jetpack Compose, SQLCipher)
│   ├── app/src/main/kotlin/com/atbm/app/
│   │   ├── domain/crypto/   # RsaBlindClient, EciesHelper, MetadataSanitizer
│   │   ├── data/            # SecureVaultDatabase (SQLCipher), NetworkClient, APIs
│   │   └── ui/              # Compose Screens (Login, Newsfeed, Whistleblower Wizard, Vault)
│   └── app/build/outputs/apk/debug/app-debug.apk # APK Android đã đóng gói
├── docs/                     # Bộ tài liệu bàn giao hoàn chỉnh
└── keys/                     # Thư mục lưu trữ cặp khóa mật mã nghiệp vụ (.pem)
```

---

## 2. Yêu Cầu Môi Trường Cài Đặt

| Thành phần | Yêu cầu tối thiểu | Khuyến nghị |
|------------|-------------------|-------------|
| Hệ điều hành | Ubuntu 22.04+ / macOS 13+ / Windows 11 (WSL2) | Linux x86_64 |
| Python | Python 3.12+ (hỗ trợ cả Python 3.14) | Python 3.12 hoặc 3.14 |
| Java / JDK | OpenJDK 17 | Eclipse Adoptium Temurin 17 |
| Android SDK | Platform 34+ (Build-Tools 34+) | Android SDK Platform 36 |
| Android Studio | Android Studio Hedgehog trở lên | Android Studio Ladybug |

---

## 3. Khởi Chạy Backend Từ Con Số 0 (Trong 5 Phút)

### Bước 1: Tạo môi trường ảo Python & Cài đặt dependencies
- **Nếu đứng tại thư mục gốc dự án (`atbm/`):**
```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```
- **Hoặc nếu `cd backend`:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Bước 2: Thiết lập cấu hình môi trường (.env)
```bash
# Từ thư mục gốc dự án:
cp backend/.env.example backend/.env

# Hoặc nếu đang trong thư mục backend:
cp .env.example .env
```
*(Lưu ý: Mọi tham số đều có giá trị mặc định an toàn cho môi trường Local Dev).*

### Bước 3: Nạp dữ liệu mẫu ban đầu (Database Seed)
Hệ thống đi kèm script tự động sinh sẵn tài khoản và bài viết mẫu:
```bash
# Chạy trực tiếp từ thư mục gốc dự án:
PYTHONPATH=backend ./backend/.venv/bin/python -m app.db.seed

# Hoặc nếu đang trong thư mục backend và đã kích hoạt virtualenv:
python -m app.db.seed
```
*Tài khoản mẫu được tạo sẵn:*
- `AD001` / `admin123`: Quản trị viên hệ thống (SYSTEM_ADMIN).
- `TT001` / `officer123`: Ban Thanh tra (COMPLIANCE_OFFICER).
- `GD001` / `director123`: Ban Giám đốc (BOARD_OF_DIRECTORS).
- `NV001` / `employee123`: Nhân viên R&D (EMPLOYEE).
- `NV002` / `employee123`: Nhân viên Kế toán (EMPLOYEE).

### Bước 4: Khởi chạy máy chủ FastAPI & Cổng Web
```bash
# Chạy trực tiếp từ thư mục gốc dự án:
PYTHONPATH=backend ./backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Hoặc nếu đang trong thư mục backend và đã kích hoạt virtualenv:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Cổng Web Portal & Quản Trị Hệ Thống:** `http://localhost:8000/` (hoặc `http://localhost:8000/admin`)
- **Tài liệu API tương tác (Swagger UI):** `http://localhost:8000/docs`

---

## 4. Kiểm Thử Hệ Thống (Testing Pipeline)

Hệ thống tuân thủ nghiêm ngặt phương pháp Test-Driven Development (TDD) với tỷ lệ bao phủ test toàn diện:

### 1. Chạy toàn bộ Unit Tests & E2E Integration:
```bash
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/ -v
```
*(Kết quả: 40/40 tests PASSED bao gồm auth, posts, compliance, anonymous submission, officer decrypt, admin web và e2e liên thông).*

### 2. Chạy Suite Kiểm thử 5 Kịch bản Bảo mật Cốt lõi:
```bash
PYTHONPATH=backend ./backend/.venv/bin/python backend/run_security_tests.py
```
*Kiểm tra 5 bài toán:*
1. Chống chữ ký mù giả mạo (Anti-Forgery Signature).
2. Kiểm tra bất biến CSDL Cụm 2 & Unlinkability (không lưu user_id hay IP; bảng quota không lưu timestamp).
3. Chống tráo đổi 1 byte file bằng chứng hoặc nội dung sau khi ký mù.
4. Tẩy sạch 100% EXIF GPS khỏi ảnh hiện trường.
5. Mô phỏng cơ chế Panic PIN (Overwrite Shredding tiêu hủy dữ liệu khẩn cấp).

---

## 5. Khởi Chạy Ứng Dụng Android

### Mở bằng Android Studio:
1. Mở Android Studio -> `Open` -> Chọn thư mục `android/`.
2. Đợi Gradle đồng bộ (Sync Project with Gradle Files).
3. Chọn thiết bị chạy (Android Emulator hoặc cắm điện thoại thật bật USB Debugging).
4. Nhấn `Run 'app'` (Shift + F10).

### Build bằng dòng lệnh (CLI):
```bash
cd android
./gradlew assembleDebug
```
*File APK đầu ra:* `android/app/build/outputs/apk/debug/app-debug.apk`.

### Chạy Unit Test Mật mã học Android:
```bash
./gradlew testDebugUnitTest
```
*(Kiểm tra tính đúng đắn toán học của `RsaBlindClient`, `EciesHelper` và `MetadataSanitizer` trên máy ảo JVM).*

---

## 6. Quy Ước Lập Trình & Nguyên Tắc An Toàn (Coding Rules)

1. **Không can thiệp ranh giới CSDL Cụm 2:**
   - Tuyệt đối không thêm cột liên kết khóa ngoại (`ForeignKey("users.id")`) hay cột định danh (`ip_address`, `client_mac`, v.v.) vào các bảng `whistle_cases`, `case_evidences`, `case_messages`.
2. **Không thêm timestamp vào bảng Quota:**
   - Bảng `blind_sign_quotas` chỉ có các cột: `id, user_id, week_epoch, request_count`. Tuyệt đối không thêm `created_at` hay `updated_at` để loại trừ hoàn toàn nguy cơ Correlation Attack so khớp thời gian.
3. **Mã hóa E2EE:**
   - Mọi nội dung tố giác và tin nhắn chat phản hồi phải được mã hóa ở phía Client (Android) trước khi đẩy lên đường truyền và lưu vào cơ sở dữ liệu.
