# Chạy hệ thống qua HTTPS/TLS

Trước đây backend chạy HTTP thuần (`http://…:8000`) và app Android bật `usesCleartextTraffic`; nay app chỉ kết nối qua HTTPS.
Nội dung hồ sơ vẫn được mã hóa ECIES ở tầng ứng dụng, nhưng JWT, mật khẩu đăng nhập và metadata
đi qua mạng ở dạng rõ. Từ phiên bản này backend hỗ trợ HTTPS với CA nội bộ.

## 1. Sinh chứng chỉ (một lần)

```bash
cd backend
source .venv/bin/activate
python scripts/gen_dev_certs.py              # SAN: localhost, 127.0.0.1, 10.0.2.2 (emulator)
python scripts/gen_dev_certs.py 192.168.1.15 # thêm IP LAN nếu chạy trên điện thoại thật
```

Script tạo:

| File | Ý nghĩa | Commit? |
|---|---|---|
| `backend/certs/ca.key` | Khóa riêng CA dev (quyền 600, chỉ nằm trên máy dev) | **Không** (đã `.gitignore`) |
| `backend/certs/server.key` | Khóa riêng TLS của server | **Không** (đã `.gitignore`) |
| `backend/certs/server.crt` | Chứng chỉ server + CA (chain) | Không |
| `backend/certs/ca.crt` | CA công khai | Không bắt buộc |
| `android/app/src/main/res/raw/atbm_dev_ca.pem` | CA mà app Android tin cậy | **Có** |

CA chỉ dùng cho phát triển và được **giữ ổn định**: lần đầu script sinh CA và lưu `ca.key` (quyền 600)
trong `backend/certs/` (đã `.gitignore`, không rời máy dev, không vào APK); các lần sau chỉ cấp lại chứng chỉ
server với SAN mới, nên APK đã cài vẫn kết nối được. Bản debug tin CA này cho mọi host (để thử qua LAN);
mọi bản build chỉ tin nó cho `10.0.2.2` / `localhost` / `127.0.0.1`.
Muốn thay CA: `python scripts/gen_dev_certs.py --new-ca` → **phải build và cài lại mọi APK**.

## 2. Chạy backend qua HTTPS

```bash
python run_https.py          # https://0.0.0.0:8443  (TLS 1.2+, chỉ ECDHE + AES-GCM/ChaCha20)
```

- Web admin: `https://localhost:8443/admin` (trình duyệt sẽ cảnh báo vì CA tự ký —
  có thể import `backend/certs/ca.crt` vào trình duyệt để hết cảnh báo).
- Khi chạy HTTPS, cookie `admin_token` tự bật cờ `Secure` và server gửi header HSTS.
- Lệnh HTTP cũ (`uvicorn app.main:app --port 8000`) vẫn dùng được cho phát triển nhanh.

Kiểm tra nhanh:

```bash
curl --cacert certs/ca.crt https://localhost:8443/health
```

## 3. App Android (đã bật sẵn)

- `AndroidManifest.xml`: `usesCleartextTraffic="false"` + `networkSecurityConfig="@xml/network_security_config"`.
- `res/xml/network_security_config.xml`: cấm cleartext toàn ứng dụng; với host backend
  (10.0.2.2 / localhost / 127.0.0.1) **chỉ** tin CA nội bộ `res/raw/atbm_dev_ca.pem` → proxy chặn bắt
  (Burp/mitmproxy) không giải mã được. Các domain khác (máy chủ thuê có chứng chỉ công khai, vd. Let's Encrypt) dùng kho CA hệ thống.
  Riêng bản **debug** có thêm `<debug-overrides>`: tin CA nội bộ cho mọi host (để thử qua IP LAN, xem mục 4);
  bản **release** chỉ tin kho CA hệ thống.
- `NetworkClient.updateBaseUrl()` từ chối mọi địa chỉ không phải `https://`; màn hình đăng nhập báo
  "Địa chỉ máy chủ không hợp lệ" nếu nhập `http://`.
- Đã gỡ `HttpLoggingInterceptor` (trước đây log BODY ghi mật khẩu/JWT ra logcat).
- Địa chỉ máy chủ: đặt lúc build bằng `./gradlew assembleRelease -Patbm.serverUrl=https://api.ten-mien-cua-ban.vn/`
  (mặc định `https://10.0.2.2:8443/` cho Emulator + backend local). Mục **Cài đặt kết nối** ở màn đăng nhập
  vẫn cho đổi tạm thời (chỉ chấp nhận https://).
- Khi thuê máy chủ: dùng chứng chỉ công khai (Let's Encrypt…) cho tên miền — app tin theo kho CA hệ thống,
  không cần nhúng CA nội bộ. Nếu muốn ghim chứng chỉ, thêm `<domain-config>` cho tên miền đó.

Đã kiểm thử (2026-11-18, Pixel 8 emulator): `http://` bị chặn; đăng nhập, gửi tố giác, nhận phản hồi
qua `https://10.0.2.2:8443`. Server chỉ bắt tay TLS 1.2/1.3 với ECDHE + AES-GCM, từ chối CBC và HTTP thuần
trên cổng 8443, có header HSTS.

## 4. Chạy thử trong mạng Wi‑Fi chung (LAN)

Dùng khi muốn cầm điện thoại thật thử app mà chưa có máy chủ thuê. **Chỉ để thử nghiệm** —
triển khai thật xem [deploy.md](deploy.md). Laptop và điện thoại phải **cùng một mạng Wi‑Fi**.

**Một lần duy nhất:**

```bash
./dev.sh certs   # nếu chưa từng sinh chứng chỉ (tạo CA dev)
./dev.sh apk     # build APK debug -> dist/cong-noi-bo.apk
```

Cài `dist/cong-noi-bo.apk`: `adb install -r dist/cong-noi-bo.apk` (cắm cáp), hoặc gửi file qua Zalo/Drive/USB
rồi mở để cài. Cùng một APK dùng được cho cả máy ảo và điện thoại thật.

**Mỗi lần thử:**

1. Trên laptop: `./dev.sh lan` (hoặc `./dev.sh lan 192.168.1.15` để chỉ định IP). Lệnh dò IP LAN, cấp lại chứng chỉ
   server nếu thiếu IP đó (giữ nguyên CA), in dòng `==> Nhập địa chỉ này vào app …: 192.168.1.38` rồi chạy HTTPS cổng 8443.
2. Mở app → **Cài đặt kết nối** (ở màn đăng nhập) → nhập **chỉ IP** vừa in, vd. `192.168.1.38`
   (app tự thêm `https://` và `:8443`) → bấm **Kiểm tra** (hoặc ✓ trên bàn phím).
3. Đăng nhập bằng tài khoản mẫu (vd. `NV001` / `employee123`).
   Web quản trị: `https://<ip>:8443/admin` — trình duyệt cảnh báo CA nội bộ là bình thường
   (muốn hết cảnh báo thì import `backend/certs/ca.crt`, đây là chứng chỉ công khai).

Ô **Cài đặt kết nối** chỉ có ở bản debug. Bản release (khi triển khai, build với `-Patbm.serverUrl=…`) ẩn ô này.

**Không kết nối được?**

- Tường lửa chặn cổng: `sudo ufw allow 8443/tcp`.
- Đổi mạng Wi‑Fi / IP laptop thay đổi → chạy lại `./dev.sh lan` và nhập IP mới vào app. **Không cần cài lại APK.**
- Chỉ phải build/cài lại APK khi sửa code app, hoặc sau khi sinh CA mới (`./dev.sh certs --new-ca`).
- Emulator vẫn dùng được như cũ qua `https://10.0.2.2:8443/`.
