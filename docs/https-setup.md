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
| `backend/certs/server.key` | Khóa riêng TLS của server | **Không** (đã `.gitignore`) |
| `backend/certs/server.crt` | Chứng chỉ server + CA (chain) | Không |
| `backend/certs/ca.crt` | CA công khai | Không bắt buộc |
| `android/app/src/main/res/raw/atbm_dev_ca.pem` | CA mà app Android tin cậy | **Có** |

Khóa riêng của CA bị hủy ngay sau khi ký nên không thể dùng CA này ký thêm chứng chỉ giả.
Chạy lại script đồng nghĩa với tạo CA mới → phải build lại app.

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
  (Burp/mitmproxy) không giải mã được. Các domain khác (vd. ngrok) dùng kho CA hệ thống.
- `NetworkClient.updateBaseUrl()` từ chối mọi địa chỉ không phải `https://`; màn hình đăng nhập báo
  "Địa chỉ máy chủ không hợp lệ" nếu nhập `http://`.
- Đã gỡ `HttpLoggingInterceptor` (trước đây log BODY ghi mật khẩu/JWT ra logcat).
- Địa chỉ máy chủ: mặc định domain ngrok (HTTPS công khai). Emulator + backend local: mở
  **Cài đặt kết nối** ở màn đăng nhập, nhập `https://10.0.2.2:8443`. Máy thật qua LAN: sinh chứng chỉ
  kèm IP (`./dev.sh certs 192.168.1.15`), build lại app, nhập `https://192.168.1.15:8443`
  (và thêm IP đó vào `domain-config` nếu muốn áp dụng chỉ-tin-CA-nội-bộ).

Đã kiểm thử (2026-11-18, Pixel 8 emulator): `http://` bị chặn; đăng nhập, gửi tố giác, nhận phản hồi
qua `https://10.0.2.2:8443`. Server chỉ bắt tay TLS 1.2/1.3 với ECDHE + AES-GCM, từ chối CBC và HTTP thuần
trên cổng 8443, có header HSTS.
