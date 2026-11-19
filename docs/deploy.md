# Triển khai lên máy chủ thuê (VPS)

Mô hình: **Caddy** (HTTPS, chứng chỉ Let's Encrypt tự động) → **uvicorn** chạy nội bộ `127.0.0.1:8000`
(systemd). Không dùng dịch vụ tunnel công cộng (ngrok…). Tệp mẫu nằm trong `deploy/`.

## 1. Chuẩn bị
- VPS Ubuntu 22.04/24.04, tối thiểu 1 vCPU / 1 GB RAM; mở cổng **80, 443** (đóng 8000/8443 với bên ngoài).
- Tên miền, ví dụ `api.ten-mien-cua-ban.vn`, bản ghi DNS **A** trỏ về IP máy chủ.

## 2. Cài mã nguồn
```bash
sudo adduser --system --group --home /opt/atbm atbm
sudo git clone https://github.com/<tai-khoan>/secure-internal-comms.git /opt/atbm
cd /opt/atbm/backend
sudo -u atbm python3 -m venv .venv && sudo -u atbm .venv/bin/pip install -r requirements.txt
sudo -u atbm cp .env.example .env && sudo chmod 600 .env
```
Sửa `/opt/atbm/backend/.env`:
| Biến | Giá trị |
|---|---|
| `JWT_SECRET_KEY` | kết quả của `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | `https://api.ten-mien-cua-ban.vn` |
| `SHOW_DEMO_ACCOUNTS` / `ENABLE_API_DOCS` | `false` |
| `LOG_FILE` | `./logs/app.log` |

## 3. Khởi tạo dữ liệu và tài khoản
```bash
cd /opt/atbm/backend
sudo -u atbm .venv/bin/python -m app.db.seed          # bảng + tài khoản mẫu (sẽ đổi mật khẩu ngay)
# Tài khoản đặc quyền chỉ cấp trên máy chủ (mật khẩu được hỏi kín):
sudo -u atbm .venv/bin/python scripts/manage_roles.py create TT100 "Họ Tên" "Ban Thanh tra" COMPLIANCE_OFFICER
sudo -u atbm .venv/bin/python scripts/manage_roles.py create AD100 "Họ Tên" "Phòng CNTT" SYSTEM_ADMIN
# Khóa hoặc đổi mật khẩu các tài khoản mẫu:
for u in AD001 TT001 GD001 NV001 NV002; do sudo -u atbm .venv/bin/python scripts/manage_roles.py lock $u; done
```
Nhân viên và Ban Giám đốc do Quản trị viên tạo trên cổng web.

## 4. Kiểm tra cấu hình
```bash
sudo -u atbm .venv/bin/python scripts/preflight.py      # mọi mục phải ĐẠT
```
Kiểm tra: khóa JWT riêng, ẩn tài khoản demo, tắt `/docs`, CORS, quyền thư mục khóa (700), không còn tài
khoản mẫu dùng mật khẩu mặc định. Dịch vụ systemd chạy `preflight --strict` trước mỗi lần khởi động và
**từ chối chạy** nếu còn mục chưa đạt.

## 5. Chạy dịch vụ
```bash
sudo cp /opt/atbm/deploy/atbm.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now atbm
sudo apt install -y caddy
sudo cp /opt/atbm/deploy/Caddyfile /etc/caddy/Caddyfile     # sửa tên miền + email
sudo systemctl reload caddy
```
Kiểm tra: `curl https://api.ten-mien-cua-ban.vn/health` → `{"status":"ok",...}`.
Web quản trị: `https://api.ten-mien-cua-ban.vn/admin`.

## 6. Build app Android trỏ về máy chủ
```bash
cd android
./gradlew assembleRelease -Patbm.serverUrl=https://api.ten-mien-cua-ban.vn/
```
App tin chứng chỉ Let's Encrypt qua kho CA hệ thống, không cần nhúng CA nội bộ.
(Ký APK bản phát hành bằng keystore riêng — không commit keystore vào git.)

## 7. Vận hành
- **Sao lưu** hằng ngày: `backend/app.db`, `backend/uploads/evidences/` (đã mã hóa) và **`backend/keys/`**
  (mất thư mục khóa = không giải mã được hồ sơ cũ). Lưu bản sao lưu khóa ở nơi tách biệt, mã hóa.
- **Log**: `backend/logs/app.log` (xoay vòng, không chứa IP). Nhật ký thao tác: trang **Nhật ký thao tác** (Ban Giám đốc).
- **Cập nhật**: `git pull` → `pip install -r requirements.txt` → `sudo systemctl restart atbm`.
- **Bảo mật**: khóa riêng của Ban Thanh tra nằm trên máy chủ — chỉ cấp quyền SSH cho người thật sự cần.
