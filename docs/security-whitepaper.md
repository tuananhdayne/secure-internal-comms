# Báo Cáo Giải Trình Mật Mã Học & An Toàn Hệ Thống (Security Whitepaper)
> **Dự án:** Secure Internal Communications & Whistleblower Engine  
> **Chuyên ngành:** An toàn Thông tin - Học viện Kỹ thuật Mật mã (KMA)  
> **Tác giả:** Nhóm Đồ án ATBM  
> **Phiên bản:** v1.0.0  

---

## 1. Bài Toán Thực Tiễn & Thách Thức Mật Mã Học

Trong các tổ chức và doanh nghiệp, việc phát hiện sai phạm, tham nhũng nội bộ thường gặp phải rào cản tâm lý lớn nhất: **Người tố cáo sợ bị trả thù, lộ danh tính**.

Nếu sử dụng các kênh tố cáo truyền thống:
- **Email / Google Form / Cổng web nội bộ thông thường:** Địa chỉ IP, Cookie, User-Agent, dấu thời gian gửi (Timestamp) đều được ghi lại vào log máy chủ.
- **Quản trị viên hệ thống (System Admin):** Nắm quyền root máy chủ, có thể truy vấn trực tiếp cơ sở dữ liệu để tìm ra nhân viên nào vừa nộp đơn tố cáo.

**Thách thức đặt ra:**
1. Làm thế nào để **xác thực** người tố cáo thực sự là nhân viên của tổ chức (không để kẻ ngoài phá hoại, spam)?
2. Làm thế nào để **ngay cả Ban Giám đốc và Quản trị viên máy chủ** cũng không thể biết hay suy luận được danh tính của người tố cáo (**Unlinkability**)?
3. Làm thế nào bảo vệ **tính toàn vẹn tuyệt đối** của hồ sơ và file bằng chứng (chống tráo đổi 1 byte dữ liệu)?

---

## 2. Chứng Minh Toán Học Thuật Toán Chữ Ký Mù RSA (David Chaum)

Hệ thống ứng dụng thuật toán **Chữ ký mù RSA** (David Chaum, 1982) để cấp phát chứng chỉ nộp hồ sơ mà không làm lộ nội dung hay danh tính.

### 2.1. Thiết lập tham số (Key Generation)
Ban Thanh tra (Compliance Officer) sở hữu cặp khóa RSA-2048 độc lập:
- Khóa công khai: $(e, N)$ với $N = p \cdot q$ ($p, q$ là hai số nguyên tố lớn an toàn).
- Khóa bí mật: $d$ thỏa mãn:
  $$e \cdot d \equiv 1 \pmod{\phi(N)}, \quad \text{với } \phi(N) = (p-1)(q-1)$$

### 2.2. Giai đoạn 1: Tính mã băm toàn vẹn $H$
Client (phía ứng dụng Android) chuẩn bị hồ sơ gồm:
- $Category$: Chuyên mục sai phạm.
- $EncTitle, EncDesc$: Tiêu đề và mô tả đã mã hóa ECIES bằng khóa công khai của Thanh tra.
- $Case\_Token$: Mã hồ sơ ngẫu nhiên 128-bit do Client tự sinh.
- $pk_{case}$: Khóa công khai EC của hồ sơ (phục vụ kênh chat E2EE sau này).
- $\{Hash(F_1), \dots, Hash(F_k)\}$: Danh sách mã băm SHA-256 của các tệp bằng chứng đính kèm (đã mã hóa AES-GCM).

Client tính mã băm ràng buộc toàn vẹn:
$$H = \text{SHA256}(Category \parallel EncTitle \parallel EncDesc \parallel Case\_Token \parallel pk_{case} \parallel Hash(F_1) \parallel \dots) \pmod N$$
*(Điều kiện: $\gcd(H, N) = 1$)*

### 2.3. Giai đoạn 2: Làm mù thông điệp ($m^*$)
Client chọn một số nguyên ngẫu nhiên bí mật $r \in \mathbb{Z}_N^*$ (gọi là **Hệ số làm mù - Blinding Factor**) sao cho $\gcd(r, N) = 1$.  
Client tính thông điệp đã làm mù:
$$m^* = (H \cdot r^e) \pmod N$$

Client gửi $m^*$ lên máy chủ Ban Thanh tra qua kết nối có xác thực danh tính nhân viên (JWT).

### 2.4. Giai đoạn 3: Ban Thanh tra ký mù ($s^*$)
Vì $m^* = (H \cdot r^e) \pmod N$ là một số nguyên ngẫu nhiên phân bố đều trong $\mathbb{Z}_N^*$, Ban Thanh tra **hoàn toàn không thể đọc hay suy đoán được giá trị $H$** bên dưới.

Ban Thanh tra kiểm tra hạn mức tuần ($K \le 5$ lượt/tuần của nhân viên). Nếu hợp lệ, thực hiện ký:
$$s^* = (m^*)^d \pmod N$$
Ban Thanh tra trả $s^*$ về cho Client.

### 2.5. Giai đoạn 4: Bóc mù thu hồi chữ ký gốc ($s$)
Client nhận $s^*$ và dùng số $r$ bí mật để bóc mù bằng nghịch đảo modulo:
$$s = (s^* \cdot r^{-1}) \pmod N$$

### 2.6. Chứng minh tính đúng đắn toán học:
Ta có:
$$s^* \equiv (m^*)^d \equiv (H \cdot r^e)^d \equiv H^d \cdot (r^e)^d \equiv H^d \cdot r^{e \cdot d} \pmod N$$
Vì $e \cdot d \equiv 1 \pmod{\phi(N)}$, theo định lý Euler:
$$r^{e \cdot d} \equiv r^1 \equiv r \pmod N$$
Do đó:
$$s^* \equiv H^d \cdot r \pmod N$$
Khi Client nhân với nghịch đảo $r^{-1}$:
$$s \equiv s^* \cdot r^{-1} \equiv (H^d \cdot r) \cdot r^{-1} \equiv H^d \pmod N$$

Khi kiểm tra bằng khóa công khai $e$:
$$s^e \equiv (H^d)^e \equiv H^{d \cdot e} \equiv H^1 \equiv H \pmod N \quad \text{(Q.E.D)}$$

$\Rightarrow$ Chữ ký $s$ là một chữ ký RSA hoàn toàn hợp lệ trên thông điệp $H$, nhưng **Ban Thanh tra chưa từng nhìn thấy $H$ hay $s$ trước đó!**

---

## 3. Chứng Minh Tính Vô Danh Không Thể Liên Kết (Unlinkability)

### Định lý Không thể Liên kết (David Chaum, 1982):
Cho bất kỳ chữ ký $s$ và thông điệp $H$ được công bố, xác suất để nó bắt nguồn từ bất kỳ lượt ký mù $m_i^*$ nào trong quá khứ là hoàn toàn đồng đều:
$$P(s \text{ bắt nguồn từ } m_i^* \mid s, H) = \frac{1}{M}, \quad \forall i \in \{1, \dots, M\}$$
*Chứng minh:*  
Với mỗi cặp $(m_i^*, s)$ bất kỳ, luôn tồn tại duy nhất một giá trị $r_i \in \mathbb{Z}_N^*$ thỏa mãn:
$$r_i \equiv s^*_i \cdot s^{-1} \pmod N$$
Do $r$ được chọn độc lập và ngẫu nhiên theo phân phối đều trên $\mathbb{Z}_N^*$, việc quan sát $m_i^*$ không cung cấp bất kỳ thông tin nào (Mutual Information $I(s; m_i^*) = 0$) để kẻ tấn công có thể liên kết chữ ký $s$ với lượt yêu cầu của nhân viên cụ thể.

---

## 4. Mô Hình Đe Dọa (Threat Model) & Phòng Ngự Đa Lớp

| Đối tượng tấn công | Khả năng & Quyền hạn | Biện pháp phòng ngự của Hệ thống |
|---|---|---|
| **Kẻ ngoài / Hacker** | Thử nộp hồ sơ giả mạo, spam hệ thống | **Chữ ký mù RSA:** Không có chữ ký $s$ hợp lệ từ Officer $\rightarrow$ Bị từ chối HTTP 400. |
| **Admin biến chất** | Quyền root máy chủ, đọc CSDL SQLite, đọc log mạng | **Kiến trúc CSDL 2 Cụm:** Cụm 2 hoàn toàn không có `user_id`, `ip_address`. Middleware tẩy sạch Header IP. |
| **Tấn công tương quan thời gian (Timing Attack)** | So khớp giờ xin chữ ký mù ở Cụm 1 với giờ nộp hồ sơ ở Cụm 2 | **1. Quota không timestamp:** Bảng `blind_sign_quotas` chỉ có cột đếm `request_count`.<br>**2. Time-Bucketing:** Cột `created_bucket` làm tròn giờ chẵn (`minute=0, second=0`). |
| **Tráo đổi file bằng chứng trên đĩa** | Admin sửa/tráo file trong thư mục `./uploads/` | **1. File Hash nhúng vào $H$:** Tráo 1 byte file $\rightarrow$ Mã băm $H$ lệch $\rightarrow$ Chữ ký $s$ sai.<br>**2. AES-256-GCM:** Toàn bộ file bằng chứng bị mã hóa bởi `File_Key` trước khi lưu trên đĩa. |
| **Lộ vị trí qua ảnh hiện trường** | File ảnh JPEG có nhúng GPS coordinates của người chụp | **Metadata Sanitizer:** Giải mã thành Raw Pixels và nén lại JPEG mới, tẩy sạch 100% EXIF & GPS. |
| **Cưỡng ép mở điện thoại (Duress Attack)** | Kẻ xấu bắt ép nhân viên mở app kiểm tra bằng chứng | **Panic PIN (999999):** Ghi đè ngẫu nhiên (Forensic Shredding) và xóa sạch DB SQLCipher trong 1 giây. |

---

## 5. Kiến Trúc Kênh Chat E2EE Ẩn Danh (Two-Way Anonymous E2EE Chat)

Sau khi hồ sơ được nộp, làm sao Ban Thanh tra có thể thẩm vấn người tố cáo mà không làm lộ danh tính?

```
[Người Tố Cáo - Mobile]                                       [Ban Thanh Tra - Officer]
        │                                                                │
        │─── 1. Sinh ngẫu nhiên Case_KeyPair (ECC P-256) ───────────────>│ (Lưu case_public_key)
        │                                                                │
        │<── 2. Officer gửi tin nhắn điều tra (Mã hóa ECIES pk_case) ────│
        │                                                                │
        │─── 3. Nhắn lại kèm Chữ ký số ECDSA (Ký bằng priv_case) ───────>│ (Xác minh tính xác thực)
```

- Ban Thanh tra gửi tin nhắn: Dùng thuật toán ECIES mã hóa bằng `case_public_key`. Chỉ người tố cáo (người nắm `case_private_key` trong SQLCipher trên máy mình) mới giải mã được.
- Người tố cáo gửi tin nhắn: Kèm chữ ký số ECDSA từ `case_private_key`. Máy chủ xác minh chữ ký khớp với `case_public_key` ban đầu, ngăn chặn kẻ thứ ba giả mạo tin nhắn.

---

## 6. Kết Luận

Kiến trúc mật mã của hệ thống kết hợp hài hòa giữa:
1. **Chữ ký mù RSA Chaum:** Bảo đảm tính vô danh (Anonymity) và tính xác thực (Authenticity).
2. **ECIES SECP256R1 + AES-256-GCM:** Bảo đảm tính bí mật (Confidentiality) và toàn vẹn (Integrity).
3. **Cơ chế Time-Bucketing & Quota No-Timestamp:** Triệt tiêu hoàn toàn tấn công tương quan thời gian (Timing Correlation Resistance).
4. **Mobile Hardening (FLAG_SECURE, Dynamic Watermark, Panic PIN):** Bảo vệ an toàn tuyệt đối cho người tố giác tại thiết bị đầu cuối.
