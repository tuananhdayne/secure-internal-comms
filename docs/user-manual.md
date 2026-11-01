# Sổ Tay Hướng Dẫn Sử Dụng Hệ Thống (User Manual)
> **Dự án:** Secure Internal Communications & Whistleblower Engine  
> **Học viện Kỹ thuật Mật mã (KMA)**  
> **Đối tượng sử dụng:** Cán bộ Nhân viên, Ban Thanh tra, Quản trị viên  
> **Phiên bản:** v1.0.0  

---

## MỤC LỤC
1. [Hướng dẫn dành cho Cán bộ Nhân viên (Employee)](#1-dành-cho-cán-bộ-nhân-viên-employee)
   - 1.1. Đăng nhập & Đổi máy chủ kết nối
   - 1.2. Đọc bảng tin nội bộ & Cơ chế Watermark động
   - 1.3. Quy trình gửi tố giác ẩn danh (Wizard 3 bước)
   - 1.4. Quản lý hồ sơ & Chat ẩn danh trong Secure Vault
   - 1.5. Chế độ khẩn cấp Panic PIN (Tiêu hủy dữ liệu)
2. [Hướng dẫn dành cho Ban Thanh tra (Compliance Officer)](#2-dành-cho-ban-thanh-tra-compliance-officer)
   - 2.1. Đăng nhập cổng thanh tra
   - 2.2. Tiếp nhận & Giải mã hồ sơ tố giác
   - 2.3. Cập nhật tiến độ điều tra & Chat phản hồi E2EE
3. [Hướng dẫn dành cho Quản trị viên Hệ thống (System Admin)](#3-dành-cho-quản-trị-viên-hệ-thống-system-admin)
   - 3.1. Đăng nhập Cổng Web Quản trị
   - 3.2. Quản lý tài khoản nhân sự (Khóa / Mở khóa)
   - 3.3. Đăng thông báo & Ghim bài viết nội bộ

---

## 1. DÀNH CHO CÁN BỘ NHÂN VIÊN (EMPLOYEE)

### 1.1. Đăng nhập & Đổi máy chủ kết nối
1. Mở ứng dụng **ATBM Secure Comms** trên điện thoại Android.
2. Màn hình đăng nhập hiển thị các trường thông tin:
   - **Mã nhân viên:** Nhập mã định danh được cấp (VD: `NV001`).
   - **Mật khẩu:** Nhập mật khẩu tài khoản (VD: `employee123`).
   - **Server Base URL:** 
     - Nếu chạy trên Android Emulator: Giữ nguyên `http://10.0.2.2:8000/`.
     - Nếu chạy trên điện thoại thật kết nối Wi-Fi LAN: Nhập địa chỉ IP máy chủ của bạn (VD: `http://192.168.1.15:8000/`).
3. Nhấn nút **"Đăng nhập An toàn"**.

> [!NOTE]
> Ứng dụng đã được kích hoạt tính năng **Chống chụp / quay màn hình (FLAG_SECURE)**. Bạn sẽ không thể chụp ảnh màn hình hoặc quay video khi đang ở trong ứng dụng.

---

### 1.2. Đọc bảng tin nội bộ & Cơ chế Watermark động
- Sau khi đăng nhập thành công, bạn được chuyển tới màn hình **Bảng Tin Nội Bộ**.
- Tại đây hiển thị các thông báo chính thức từ Ban Giám đốc và chính sách an toàn thông tin.
- **Quan sát Watermark động:** Trên toàn bộ màn hình sẽ có dòng chữ in chìm mờ chéo góc:  
  `ATBM CONFIDENTIAL • [HỌ TÊN NHÂN VIÊN] (MÃ NV) • [NGÀY GIỜ HIỆN TẠI]`
- **Mục đích an toàn:** Dòng chữ này ngăn chặn hoàn toàn việc chụp lén màn hình bằng điện thoại khác; nếu ảnh bị rò rỉ ra ngoài, ban an ninh sẽ lập tức truy vết được danh tính người chụp dựa trên mã nhân viên và mốc thời gian in chìm.
- Bạn có thể nhấn vào bất kỳ bài viết nào để đọc chi tiết và gửi bình luận đóng góp ý kiến.

---

### 1.3. Quy trình gửi tố giác ẩn danh (Wizard 3 bước)
Nhấn vào biểu tượng chiếc khiên **🛡️** ở góc trên bên phải màn hình để mở **Cổng Tố Giác Ẩn Danh**.

Quy trình nộp hồ sơ gồm 3 bước minh bạch:
- **Bước 1: Nhập thông tin vụ việc:**
  - Chọn danh mục sai phạm: *Tham nhũng tài chính*, *Quấy rối công sở*, *Vi phạm an toàn thông tin*, v.v.
  - Nhập **Tiêu đề** vụ việc ngắn gọn, rõ ràng.
  - Nhập **Mô tả chi tiết** các dấu hiệu vi phạm và bằng chứng thu thập được.
  - Nhấn nút *"Tiếp Tục"*.
- **Bước 2: Mã hóa ECIES & Làm sạch Bằng chứng:**
  - Ứng dụng tự động kích hoạt thuật toán **ECIES SECP256R1** để mã hóa toàn bộ tiêu đề và nội dung mô tả bằng khóa công khai của Ban Thanh tra.
  - Tệp hình ảnh bằng chứng được module **Metadata Sanitizer** tẩy sạch 100% tọa độ vị trí GPS và thông tin dòng máy điện thoại.
  - Ứng dụng sinh một cặp khóa EC mới độc lập dành riêng cho vụ việc này.
  - Nhấn nút *"Xác Nhận & Sang Bước 3"*.
- **Bước 3: Ký Mù RSA Chaum & Nộp Ẩn Danh:**
  - Ứng dụng tính mã băm toán học $H$, nhân với hệ số ngẫu nhiên bí mật $r$ để tạo thông điệp làm mù $m^*$.
  - Ứng dụng gửi $m^*$ lên máy chủ để xin Chữ ký mù từ Ban Thanh tra. (Ban Thanh tra kiểm tra bạn là nhân viên hợp lệ nhưng hoàn toàn KHÔNG THỂ THẤY nội dung tố giác bên dưới).
  - Nhận chữ ký mù $s^*$, ứng dụng tự bóc mù để lấy chữ ký hợp lệ $s$.
  - Ứng dụng tự động lưu hồ sơ vào **Secure Vault** trên máy và gửi gói tin tố giác nặc danh lên máy chủ mà không gửi kèm bất kỳ thông tin danh tính nào.
  - Màn hình thông báo: *"✅ Nộp hồ sơ tố giác ẩn danh thành công! Token: CASE-..."*.

---

### 1.4. Quản lý hồ sơ & Chat ẩn danh trong Secure Vault
Nhấn vào biểu tượng chiếc hòm **🗄️** ở thanh công cụ để mở **Secure Vault**:
- Mọi hồ sơ tố giác bạn từng gửi đều được lưu trữ an toàn trong cơ sở dữ liệu **SQLCipher** (Mã hóa phần cứng AES-256) trên bộ nhớ máy điện thoại.
- Nhấn vào từng vụ việc để:
  - Xem trạng thái xử lý từ Ban Thanh tra: `PENDING` (Chờ thụ lý), `UNDER_INVESTIGATION` (Đang điều tra), `RESOLVED` (Đã xử lý).
  - **Chat 2 chiều ẩn danh (E2EE):** Đọc tin nhắn phản hồi từ Thanh tra viên (nội dung được giải mã tự động bằng khóa riêng của vụ việc) và gửi tin nhắn cung cấp thêm chứng cứ mà vẫn hoàn toàn giấu tên.

---

### 1.5. Chế độ khẩn cấp Panic PIN (Tiêu hủy dữ liệu)
Trong trường hợp bị kẻ xấu cưỡng ép, đe dọa yêu cầu mở điện thoại để kiểm tra ứng dụng:
1. Nhấn vào biểu tượng còi báo động **🚨** ở góc trên màn hình Secure Vault.
2. Hộp thoại cảnh báo khẩn cấp xuất hiện.
3. Nhập mã **PANIC PIN**: `999999`.
4. Nhấn **"XÁC NHẬN TIÊU HỦY"**:
   - Ứng dụng lập tức thực thi kỹ thuật **Forensic Shredding**: Ghi đè toàn bộ file cơ sở dữ liệu SQLite bằng các byte ngẫu nhiên rồi xóa vĩnh viễn khỏi bộ nhớ máy.
   - Toàn bộ Private Keys, Case Tokens biến mất hoàn toàn không thể phục hồi bằng các phần mềm phục hồi dữ liệu chuyên dụng.
   - Ứng dụng tự động đăng xuất và chuyển về màn hình đăng nhập sạch sẽ, bảo đảm an toàn tính mạng và bảo mật tuyệt đối cho bạn.

---

## 2. DÀNH CHO BAN THANH TRA (COMPLIANCE OFFICER)

### 2.1. Đăng nhập cổng thanh tra
- Sử dụng tài khoản Ban Thanh tra:
  - Mã nhân viên: `TT001`
  - Mật khẩu: `officer123`

### 2.2. Tiếp nhận & Giải mã hồ sơ tố giác
- Ban Thanh tra truy cập danh sách các vụ việc mới nộp qua API hoặc giao diện quản lý.
- **Quy trình giải mã:**
  - Tiêu đề và mô tả của hồ sơ được bảo vệ bằng thuật toán ECIES.
  - Ban Thanh tra sử dụng Khóa bí mật EC (`Officer_Chat_PrivateKey`) được bảo vệ nghiêm ngặt trên máy chủ để giải mã nội dung bản rõ.
  - Tải về tệp bằng chứng và dùng khóa đối xứng `File_Key` đính kèm để giải mã file xem nội dung.

### 2.3. Cập nhật tiến độ điều tra & Chat phản hồi E2EE
- Ban Thanh tra cập nhật trạng thái vụ việc sang `UNDER_INVESTIGATION` để người tố giác yên tâm theo dõi.
- Thanh tra viên có thể soạn tin nhắn thẩm vấn, làm rõ chi tiết sai phạm. Tin nhắn được mã hóa ECIES bằng `case_public_key` trước khi gửi, bảo đảm chỉ có đúng người nộp đơn mới đọc được.

---

## 3. DÀNH CHO QUẢN TRỊ VIÊN HỆ THỐNG (SYSTEM ADMIN)

### 3.1. Đăng nhập Cổng Web Quản trị
- Truy cập trình duyệt web tại địa chỉ: `http://localhost:8000/admin/login`
- Nhập thông tin quản trị:
  - Mã nhân viên: `AD001`
  - Mật khẩu: `admin123`
- Nhấn **"Xác thực & Đăng nhập"**.

### 3.2. Quản lý tài khoản nhân sự
- Vào mục **"Nhân sự"**:
  - Xem danh sách toàn bộ cán bộ nhân viên trong công ty.
  - Thêm tài khoản nhân viên mới: Nhập Mã NV, Họ tên, Phòng ban, Vai trò và Mật khẩu khởi tạo.
  - Khóa tài khoản: Nhấn nút **"Khóa"** đối với nhân viên vi phạm kỷ luật hoặc đã nghỉ việc; tài khoản sẽ bị vô hiệu hóa ngay lập tức.
  - Mở khóa tài khoản: Nhấn nút **"Mở khóa"** để khôi phục quyền truy cập.

### 3.3. Đăng thông báo & Ghim bài viết nội bộ
- Vào mục **"Truyền thông"**:
  - Nhập **Tiêu đề** và **Nội dung** thông báo chính thức.
  - Tích chọn *"Ghim bài viết lên đầu trang bảng tin Mobile"* nếu đây là quy định quan trọng.
  - Nhấn **"Đăng Thông Báo"**; bài viết sẽ lập tức xuất hiện trên ứng dụng di động của toàn bộ nhân viên.
  - Có thể xóa các thông báo cũ bằng nút **"Xóa"**.

> [!WARNING]
> **RÀNG BUỘC KIẾN TRÚC MẬT MÃ ATBM:**
> Quản trị viên hệ thống (System Admin) chỉ có thẩm quyền quản lý tài khoản định danh và bảng tin. Quản trị viên **TUYỆT ĐỐI KHÔNG THỂ** giải mã, đọc trộm nội dung hay can thiệp vào các hồ sơ tố giác sai phạm ẩn danh của nhân viên.
