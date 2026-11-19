# Kiến trúc mã nguồn & hướng dẫn gỡ lỗi

Tài liệu này trả lời ba câu hỏi: **code nằm ở đâu**, **một request đi qua những file nào**, và
**khi có lỗi thì xem ở đâu**. Các lệnh nhắc đến đều có trong `dev.sh` (`./dev.sh help`).

---

## 1. Sơ đồ thư mục

```text
atbm/
├── dev.sh                    # ./dev.sh run | run-https | test | test-security | seed | reset-db ...
├── backend/
│   ├── app/
│   │   ├── main.py           # LẮP RÁP app: middleware, static, router. Đọc file này đầu tiên.
│   │   ├── core/             # Hạ tầng dùng chung, không chứa nghiệp vụ
│   │   │   ├── config.py     #   Đường dẫn, JWT, quota... (đọc từ backend/.env)
│   │   │   ├── constants.py  #   Role, CaseStatus, SenderType — KHÔNG gõ tay chuỗi vai trò/trạng thái
│   │   │   ├── security.py   #   bcrypt + JWT
│   │   │   ├── logging.py    #   Định dạng log, request_id, che case_token, tắt access log uvicorn
│   │   │   └── middleware.py #   request_id, xóa header IP, log an toàn, header bảo mật, bắt lỗi 500
│   │   ├── crypto/           # Toán mật mã thuần (không biết gì về HTTP / CSDL)
│   │   │   ├── blind_signature.py  # Ký mù RSA Chaum, parse_rsa_int()
│   │   │   ├── ecies.py            # ECDH P-256 + HKDF-SHA256 + AES-256-GCM
│   │   │   ├── key_manager.py      # Sinh / nạp khóa của Ban Thanh tra (backend/keys/)
│   │   │   └── sanitizer.py        # Tẩy EXIF/GPS khỏi ảnh
│   │   ├── services/         # NGHIỆP VỤ dùng chung giữa REST API và Web Admin
│   │   │   ├── case_crypto.py      # Giải mã hồ sơ/tin nhắn, mã hóa phản hồi của Thanh tra
│   │   │   └── evidence.py         # Lưu tệp bằng chứng: tẩy EXIF, SHA-256, lọc tên/MIME
│   │   ├── models/           # SQLAlchemy: identified.py (Cụm 1) | anonymous.py (Cụm 2)
│   │   ├── schemas/          # Pydantic: dữ liệu vào/ra của REST API
│   │   ├── db/               # session.py (engine, get_db) | seed.py (dữ liệu mẫu)
│   │   └── api/              # TẦNG HTTP — chỉ đọc request, kiểm quyền, gọi services, trả response
│   │       ├── deps.py       #   get_current_user (JWT Bearer), require_role
│   │       ├── admin_web.py  #   Web Admin /admin/* (Jinja2, cookie JWT, _guard())
│   │       └── v1/           #   REST API /api/v1/*
│   │           ├── auth.py, posts.py, compliance.py   # Cụm 1 (định danh)
│   │           └── anonymous.py, officer.py           # Cụm 2 (ẩn danh / Thanh tra)
│   ├── scripts/gen_dev_certs.py   # Sinh chứng chỉ TLS dev
│   ├── run_https.py               # Chạy uvicorn với TLS
│   ├── run_security_tests.py      # 5 kịch bản bảo mật cốt lõi
│   └── tests/
│       ├── conftest.py       # Ép test dùng CSDL + uploads TẠM (không bao giờ đụng app.db)
│       ├── whitebox/         # Toán mật mã, ORM, deps
│       ├── blackbox/         # REST API, Web Admin, RBAC, hồi quy bảo mật
│       └── performance/      # Benchmark (chạy tay)
├── frontend/
│   ├── templates/            # Jinja2: base.html (khung), _icons.html (macro icon), 1 file / trang
│   └── static/
│       ├── css/              # admin.css (hệ thiết kế chung), login.css, cases.css
│       └── js/               # admin.js (menu), login.js, cases.js (modal Thanh tra)
├── android/                  # App Kotlin + Jetpack Compose (xem mục 6)
├── scripts/flatten_kotlin_layout.sh
└── docs/
```

**Quy tắc phân tầng** (theo chiều phụ thuộc, chỉ được import "xuống dưới"):

```
api/ (HTTP)  ──►  services/ (nghiệp vụ)  ──►  crypto/ (toán)   models/ (CSDL)   core/ (hạ tầng)
```

- Code mới cần cả REST API lẫn Web Admin dùng → đặt ở `services/`, không chép sang hai route.
- Route không tự giải mã / tự xử lý tệp; route chỉ kiểm quyền và gọi service.
- `crypto/` không import FastAPI hay SQLAlchemy để test toán thuần dễ dàng.

---

## 2. Hai cụm dữ liệu và ranh giới ẩn danh

| | Cụm 1 — Định danh | Cụm 2 — Ẩn danh |
|---|---|---|
| Bảng | `users`, `posts`, `comments`, `blind_sign_quotas` | `whistle_cases`, `case_evidences`, `case_messages` |
| Xác thực | JWT (`Authorization: Bearer`) / cookie `admin_token` | Không có. Quyền sở hữu hồ sơ = chữ ký ECDSA bằng khóa của hồ sơ |
| Route | `/api/v1/auth`, `/posts`, `/compliance`, `/admin/*` | `/api/v1/anonymous/*` (người tố giác), `/api/v1/officer/*`, `/admin/cases*` (Thanh tra) |

**Không bao giờ** thêm cột/log có thể nối hai cụm với nhau: `user_id`, IP, User-Agent, timestamp chính
xác của hồ sơ, hay ghi `case_token` vào log. Middleware và `core/logging.py` đã chặn phần log; khi viết
code mới trong `api/v1/anonymous.py` hãy giữ nguyên tắc này.

---

## 3. Luồng request chính (file nào chạy, theo thứ tự)

### 3.1 Nộp hồ sơ tố giác (app Android → `POST /api/v1/anonymous/cases`)

1. App xin chữ ký mù: `POST /api/v1/compliance/blind-sign` → `api/v1/compliance.py`
   → kiểm quota tuần (`BlindSignQuota`) → `BlindSignatureEngine.blind_sign()`.
2. App bóc mù, mã hóa ECIES nội dung, tẩy EXIF ảnh, rồi nộp multipart.
3. `core/middleware.py` xóa header IP, KHÔNG ghi access log.
4. `api/v1/anonymous.py::submit_anonymous_case`
   → `services/evidence.store_uploads()` (tẩy EXIF, SHA-256, lọc tên/MIME, ghi `uploads/evidences/`)
   → `BlindSignatureEngine.compute_payload_hash()` → `verify(H, s)`
   → sai: `evidence.discard()` + HTTP 400 · đúng: lưu `WhistleCase` với `created_bucket` làm tròn giờ.

### 3.2 Thanh tra mở hồ sơ trên web (`/admin/cases` → modal)

1. `admin_web.py::cases_page` (`_guard` vai trò `COMPLIANCE_OFFICER`) render `cases.html`.
2. Bấm "Thụ lý & giải mã" → `static/js/cases.js::openCaseModal()` gọi `GET /admin/cases/{id}/decrypt`.
3. `admin_web.py::decrypt_case_json` → `services/case_crypto.decrypt_case_payload()` +
   `officer_message_view()` cho từng tin nhắn → JSON (có cờ `decrypted`).
4. `cases.js` dựng DOM bằng `textContent` (không bao giờ `innerHTML` với dữ liệu).
5. Gửi phản hồi → `POST /admin/cases/{id}/reply` → `case_crypto.build_officer_reply()` (ECIES tới khóa
   của hồ sơ + bản sao `ENC:` cho Thanh tra) → redirect `?active_case_id=` để modal tự mở lại.

### 3.3 Đăng nhập Web Admin

`POST /admin/login` → `admin_web.py::login_submit` → cookie `admin_token` (HttpOnly, SameSite=Lax,
`Secure` khi HTTPS, hết hạn cùng JWT 15 phút). Mọi trang gọi `get_current_admin()` → vai trò được kiểm
lại theo CSDL mỗi request.

---

## 4. Gỡ lỗi

### 4.1 Đọc log và `request_id`

```
2026-11-18 16:44:22 INFO  [b4cd031a5c9f] app.access: GET /admin/cases -> 200 (27.5 ms)
                           └─ request_id
```

- Mọi response có header `X-Request-ID`. JSON lỗi 500 cũng có trường `request_id`; trên trang Thanh tra
  lỗi hiển thị kèm "mã tra log".
- Tìm traceback: `grep b4cd031a5c9f <file log>` → dòng `app.error` chứa traceback đầy đủ.
- Bật log chi tiết: `./dev.sh run-debug` (hoặc `LOG_LEVEL=DEBUG`).
- Request tới `/api/v1/anonymous` **cố ý không có access log**. Khi lỗi 5xx, log chỉ có đường dẫn đã che:
  `/api/v1/anonymous/cases/{case_token}`.

### 4.2 Triệu chứng → chỗ cần xem

| Triệu chứng | Nguyên nhân thường gặp | Xem ở đâu |
|---|---|---|
| Nộp hồ sơ trả 400 "Chữ ký mù không hợp lệ…" | H phía client ≠ H server: thứ tự/trim trường khác, hash tệp khác (ảnh còn EXIF nên server tẩy → hash đổi), khóa RSA đã sinh lại | `crypto/blind_signature.compute_payload_hash`, `services/evidence._strip_exif_if_present`, `backend/keys/` |
| 400 "Định dạng chữ ký mù không hợp lệ" | Gửi số hex không có `0x` nhưng chỉ toàn chữ số 0-9 | `crypto/blind_signature.parse_rsa_int` |
| Nộp hồ sơ trả 413 | Tệp > `MAX_EVIDENCE_FILE_MB` (50) hoặc > `MAX_EVIDENCE_FILES` (10) tệp | `core/config.py`, `services/evidence.py` |
| Gửi tin nhắn ẩn danh trả 409 | Gửi lại đúng gói tin cũ (cùng chữ ký) — chống replay; client phải ký lại mỗi lần gửi | `api/v1/anonymous.send_anonymous_message` |
| Log khởi động cảnh báo `JWT_SECRET_KEY` | Đang dùng khóa mặc định công khai → ai cũng tự ký được token Admin | đặt khóa ngẫu nhiên ≥ 32 ký tự trong `backend/.env` |
| 429 khi xin chữ ký mù | Hết quota 5 lượt/tuần | `WEEKLY_BLIND_SIGN_QUOTA` trong `core/config.py`, bảng `blind_sign_quotas` |
| Modal hiện "Chưa thể giải mã" | Hồ sơ mã hóa bằng khóa EC cũ (đã xóa `backend/keys/`) hoặc payload hỏng | log WARNING `app.services.case_crypto` (có id hồ sơ) |
| Tin nhắn người tố giác bị 400 "Chữ ký số…" | Ký sai chuỗi: phải ký đúng `encrypted_message` (hex) bằng khóa riêng của hồ sơ | `api/v1/anonymous.send_anonymous_message` |
| Đăng nhập web đúng mật khẩu vẫn báo sai | Tài khoản không phải ADMIN/OFFICER, hoặc mật khẩu demo đã bị test cũ đổi | `admin_web.login_submit`; `./dev.sh reset-db` |
| Bị đá về trang đăng nhập sau ~15 phút | JWT hết hạn (đúng thiết kế) | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| 403 JSON "Truy cập bị từ chối…" trên web | Sai vai trò cho thao tác | `_guard(...)` trong route tương ứng của `admin_web.py` |
| App Android không kết nối HTTPS | Thiếu SAN cho IP đang dùng, app chưa build lại sau `./dev.sh certs`, BASE_URL vẫn `http://` | `docs/https-setup.md` |
| Giao diện web lỗi JS | Mở DevTools > Console; tệp nguồn ở `frontend/static/js/` | `cases.js`, `admin.js` |

### 4.3 Test

```bash
./dev.sh test        # 67 test, CSDL tạm
./dev.sh test-fast   # dừng ở lỗi đầu tiên, in chi tiết
cd backend && .venv/bin/python -m pytest tests/blackbox/test_security_regressions.py -vv   # một file
```

`tests/conftest.py` đặt `DATABASE_URL` / `UPLOAD_DIR` sang thư mục tạm **trước khi** import `app`,
nên test có `drop_all` cũng không xóa được `backend/app.db`. Không import `app` ở đầu file test
trước conftest (pytest tự nạp conftest trước).

---

## 5. Thêm tính năng mới — làm ở đâu?

| Muốn… | Làm ở |
|---|---|
| Thêm endpoint REST | `api/v1/<module>.py` + schema trong `schemas/`; logic dùng chung → `services/` |
| Thêm trang Web Admin | route trong `admin_web.py` (dùng `_guard`), template trong `frontend/templates/`, CSS/JS riêng trong `frontend/static/` |
| Thêm vai trò / trạng thái | `core/constants.py` (một chỗ duy nhất) |
| Thêm thuật toán mật mã | `crypto/` (thuần, có test whitebox) |
| Thêm cấu hình | `core/config.py` + `backend/.env.example` |

---

## 6. App Android

Mã nguồn: `android/app/src/main/kotlin/`. Sau khi chạy `./dev.sh flatten-kotlin`, đường dẫn bỏ phần
`com/atbm/app` (package trong file giữ nguyên `com.atbm.app...`, theo khuyến nghị của Kotlin):

```text
kotlin/
├── MainActivity.kt
├── data/api/        # Retrofit: AnonymousApi, IdentifiedApi, Models, NetworkClient (BASE_URL)
├── data/db/         # SecureVaultDatabase (SQLCipher)
├── domain/crypto/   # EciesHelper, RsaBlindClient, MetadataSanitizer — phải khớp backend/app/crypto
├── domain/notification/
└── ui/              # theme, components (DynamicWatermark), screens (Login, Newsfeed, Vault, Whistleblower)
```

Gỡ lỗi kết nối: Android Studio → Logcat, lọc tag `OkHttp` (logging interceptor) và đối chiếu
`X-Request-ID` trong response với log backend.
