# Giao thức nộp hồ sơ ẩn danh (dành cho người bảo trì)

Giao thức do dự án tự định nghĩa và **phải khớp từng byte** giữa app Android (Kotlin) và server
(Python). Mọi thay đổi phải sửa **cả hai bên cùng lúc** và sinh lại bộ dữ liệu kiểm thử dùng chung.

| Thành phần | Android | Server |
|---|---|---|
| Thông điệp ký mù + RFC 9474 | `domain/crypto/RsaBlindClient` (`payloadMessage`, `blind`, `finalize`) | `app/crypto/blind_signature.py` (`payload_message`, `BlindSignatureEngine`) |
| ECIES | `domain/crypto/EciesHelper` | `app/crypto/ecies.py` |
| Luồng gửi | `domain/submission/WhistleblowerSubmission.kt` | `app/api/v1/anonymous.py` `submit_anonymous_case` |
| Dữ liệu kiểm thử | `src/test/.../ProtocolVectorsTest.kt` | `tests/blackbox/test_protocol_vectors.py` |

Bộ dữ liệu: `protocol/test_vectors.json` (khóa thử, sinh bằng `backend/scripts/gen_protocol_vectors.py`).
Chạy kiểm tra: `./dev.sh test` (server) và `cd android && ./gradlew testDebugUnitTest` (app).

## Các bước (app)

1. Lấy khóa công khai Ban Thanh tra: `GET /api/v1/compliance/public-keys` → RSA `(e, n)` + EC `chat_pub_hex`.
2. Sinh cặp khóa EC P-256 riêng cho hồ sơ và mã hồ sơ `CASE-` + 32 hex ngẫu nhiên (server từ chối mã < 24 ký tự chữ-số).
3. Mã hóa `tiêu đề + "|||" + mô tả` (UTF-8) bằng ECIES tới `chat_pub_hex`.
   - `encrypted_description` = ciphertext hex đầy đủ; `encrypted_title` = 32 ký tự hex đầu của ciphertext (chỉ để tương thích cột cũ, không mang thông tin riêng).
4. Với mỗi tệp: ảnh được xóa EXIF/GPS **trước** khi băm; tính SHA-256 hex của byte sẽ gửi.
   Không có tệp nào → app gửi một tệp giữ chỗ `evidence_<ms>.bin` (server đánh dấu MIME `application/x-atbm-placeholder` và ẩn khỏi giao diện).
5. Dựng **thông điệp** `msg` (xem dưới) rồi làm mù theo **RFC 9474** (RSABSSA-SHA384-PSS-Deterministic):
   `m = OS2IP(EMSA-PSS-ENCODE(msg))` (SHA-384, MGF1-SHA384, salt 48 byte ngẫu nhiên), `m* = m · r^e mod n`;
   gửi `"0x" + hex(m*)` tới `POST /api/v1/compliance/blind-sign` (có JWT, trừ 1 lượt/tuần).
6. Server trả `s* = m*^d mod n` (đã tự kiểm tra `s*^e == m*`). App bóc mù `s = s* · r⁻¹ mod n` và **kiểm tra
   `s^e mod n == m`** trước khi dùng, rồi gửi multipart **không kèm JWT** tới `POST /api/v1/anonymous/cases`.
7. Server dựng lại `msg` và xác minh `s` là chữ ký **RSASSA-PSS chuẩn** của `msg` (thư viện `cryptography`).

## Thông điệp được ký

```
msg = category | enc_title | enc_desc | case_token | case_pubkey_hex | sha_1 | ... | sha_k     (bytes UTF-8)
```

- Mỗi trường được **trim** khoảng trắng hai đầu rồi mã hóa UTF-8; dấu phân cách là byte `|`.
- `sha_i` là SHA-256 hex chữ thường của từng tệp, **sắp xếp tăng dần** (thứ tự tải lên không quan trọng).
- Vì sao: chữ ký ràng buộc nội dung + mã hồ sơ + khóa hồ sơ + từng tệp, nên tráo bất kỳ thành phần nào
  sau khi ký đều làm chữ ký vô hiệu.
- Vì sao RFC 9474 thay cho RSA "trơn" (`s^e == SHA256(...) mod n`) trước đây: RSA trơn có tính nhân và giá trị
  băm 256 bit không phủ miền 2048 bit; với PSS, chữ ký cuối cùng là chữ ký RSA-PSS tiêu chuẩn.
  **App phiên bản cũ (RSA trơn) không gửi được nữa** — phải cài APK mới.

## ECIES

`ECDH(P-256)` → `HKDF-SHA256(salt = 32 byte 0, info = "atbm-ecies-aes256gcm", 32 byte)` → `AES-256-GCM`
(IV 12 byte, tag 16 byte tách riêng). Khóa công khai: điểm không nén 65 byte (`04‖X‖Y`) dạng hex; khóa riêng
trên app: PKCS#8 DER hex.

## Kênh trao đổi

- Người tố giác → Thanh tra: ECIES tới `chat_pub_hex`, ký `SHA256withECDSA` (DER hex) bằng khóa riêng hồ sơ
  trên **chuỗi `ciphertext` hex** (UTF-8); server kiểm tra chữ ký bằng `case_public_key`.
- Thanh tra → người tố giác: server mã hóa ECIES tới `case_public_key`; một bản sao mã hóa tới khóa
  Ban Thanh tra được lưu trong cột `digital_signature` với tiền tố `ENC:` để Thanh tra đọc lại lịch sử.

## Những điều KHÔNG được làm

- Đổi thứ tự trường, dấu phân cách, cách trim hay chữ hoa/thường của hash ở một bên.
- Thêm mốc thời gian vào bảng `blind_sign_quotas` hoặc ghi log hoạt động xin chữ ký (phá tính không liên kết).
- Ghi IP hoặc `case_token` vào log (xem `app/core/logging.py`).
