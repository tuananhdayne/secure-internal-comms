# Hướng Dẫn Sử Dụng — Cổng Nội Bộ

> **Sản phẩm:** Cổng Nội Bộ — Bảng tin công ty & kênh tố giác an toàn
> **Đối tượng:** Nhân viên (ứng dụng Android), Ban Thanh tra và Quản trị viên (cổng web)
> **Phiên bản:** v1.1.0

Tài liệu này dành cho người dùng cuối. Chi tiết kỹ thuật và cơ chế bảo mật xem tại
[`security-whitepaper.md`](security-whitepaper.md), cài đặt và vận hành xem tại
[`developer-guide.md`](developer-guide.md) và [`https-setup.md`](https-setup.md).

---

## MỤC LỤC
1. [Dành cho Nhân viên (ứng dụng Android)](#1-dành-cho-nhân-viên-ứng-dụng-android)
   - 1.1. Đăng nhập
   - 1.2. Bảng tin
   - 1.3. Gửi tố giác ẩn danh
   - 1.4. Theo dõi tố giác & trao đổi với Ban Thanh tra
   - 1.5. Xóa nhanh dữ liệu trên máy
2. [Dành cho Ban Thanh tra (cổng web)](#2-dành-cho-ban-thanh-tra-cổng-web)
3. [Dành cho Quản trị viên (cổng web)](#3-dành-cho-quản-trị-viên-cổng-web)
4. [Câu hỏi thường gặp](#4-câu-hỏi-thường-gặp)

---

## 1. DÀNH CHO NHÂN VIÊN (ỨNG DỤNG ANDROID)

### 1.1. Đăng nhập
1. Mở ứng dụng **Cổng Nội Bộ**.
2. Nhập **Mã nhân viên** và **Mật khẩu** do công ty cấp, nhấn **Đăng nhập**.
3. Quên mật khẩu hoặc tài khoản bị khóa: liên hệ bộ phận Nhân sự / Quản trị viên.

> [!NOTE]
> Mục **Cài đặt kết nối** ở cuối màn hình đăng nhập chỉ dùng khi bộ phận kỹ thuật hướng dẫn.
> Ứng dụng chỉ chấp nhận địa chỉ máy chủ bắt đầu bằng `https://`.

> [!NOTE]
> Để bảo vệ thông tin, ứng dụng **không cho phép chụp hoặc quay màn hình**.

### 1.2. Bảng tin
- Hiển thị thông báo, chính sách và tin tức của công ty; bài quan trọng có nhãn **Đã ghim**.
- Nhấn vào bài viết để đọc toàn bộ và gửi bình luận.
- Màn hình bảng tin có chữ chìm mờ ghi tên bạn và thời gian xem — đây là quy định bảo mật
  tài liệu nội bộ, giúp phát hiện nếu tài liệu bị chụp lại bằng thiết bị khác.

### 1.3. Gửi tố giác ẩn danh
Nhấn nút **Gửi tố giác** ở góc dưới bên phải màn hình bảng tin. Quy trình gồm 3 bước:

1. **Nội dung**
   - Chọn vấn đề: *Tham nhũng tài chính*, *Quấy rối công sở*, *Vi phạm an toàn thông tin*,
     *Gian lận đấu thầu* hoặc *Khác*.
   - Nhập **Tiêu đề ngắn gọn** và **Mô tả chi tiết** (sự việc gì, khi nào, ở đâu, ai liên quan).
   - Có thể đính kèm **Ảnh/Video**, **Ghi âm** hoặc **Tài liệu** (không bắt buộc).
2. **Xem lại** — kiểm tra lại nội dung trước khi gửi; nhấn **Sửa lại** nếu cần.
3. **Gửi đi** — nhấn **Gửi tố giác**. Sau khi gửi thành công, ứng dụng chuyển sang mục
   **Tố giác của tôi**.

**Thông tin của bạn được bảo vệ thế nào?**
- Không ai biết bạn là người gửi — kể cả Ban Thanh tra và Quản trị viên.
- Nội dung được khóa ngay trên điện thoại, chỉ Ban Thanh tra mở được.
- Thông tin vị trí và thiết bị trong ảnh được tự động xóa trước khi gửi.

> [!NOTE]
> Mỗi nhân viên được gửi tối đa **5 tố giác mỗi tuần**.

### 1.4. Theo dõi tố giác & trao đổi với Ban Thanh tra
- Mở bằng biểu tượng **hộp lưu trữ** trên thanh tiêu đề bảng tin, hoặc nút
  **Theo dõi tố giác đã gửi** ở màn hình đăng nhập (không cần đăng nhập).
- Mỗi tố giác có một **mã ngắn** (ví dụ `#984047`) — Ban Thanh tra nhìn thấy cùng mã này.
- Trạng thái: **Đã gửi** → **Chờ tiếp nhận** → **Đang xử lý** → **Đã xử lý xong** / **Không chấp nhận**.
- Khi Ban Thanh tra phản hồi hoặc đổi trạng thái, bảng tin hiện thông báo
  **"Có phản hồi mới từ Ban Thanh tra"** và điện thoại nhận thông báo.
- Nhấn vào tố giác để đọc tin nhắn và gửi thêm thông tin. Danh tính của bạn vẫn được giữ kín.

> [!IMPORTANT]
> Tố giác chỉ được lưu trên **chính điện thoại đã gửi**. Nếu gỡ ứng dụng hoặc đổi máy,
> bạn sẽ không theo dõi được các tố giác cũ.

### 1.5. Xóa nhanh dữ liệu trên máy
Dùng khi bạn cần xóa ngay mọi dấu vết tố giác trên điện thoại (ví dụ: bị ép buộc mở máy).
1. Trong **Tố giác của tôi**, nhấn biểu tượng **thùng rác đỏ** ở góc trên.
2. Nhập **mã khẩn cấp** do bộ phận phụ trách cung cấp khi bàn giao (mặc định: `999999`).
3. Nhấn **Xóa dữ liệu**. Toàn bộ tố giác đã lưu trên máy bị xóa vĩnh viễn, ứng dụng quay về
   màn hình đăng nhập. Thao tác **không thể khôi phục**.

---

## 2. DÀNH CHO BAN THANH TRA (CỔNG WEB)

### 2.1. Đăng nhập
Mở trình duyệt tới địa chỉ cổng quản trị do bộ phận kỹ thuật cung cấp
(ví dụ `https://<máy-chủ>:8443/admin`), đăng nhập bằng tài khoản Cán bộ Thanh tra.

### 2.2. Xem và xử lý hồ sơ
- Trang **Hồ sơ tố giác** hiển thị số liệu tổng hợp và danh sách hồ sơ. Lọc theo trạng thái
  hoặc tìm theo mã hồ sơ / chuyên mục.
- **Thời gian gửi** được làm tròn theo giờ để bảo vệ người gửi.
- Nhấn **Xem & xử lý** để mở hồ sơ:
  - **Nội dung tố giác**: tiêu đề và mô tả chi tiết.
  - **Bằng chứng đính kèm**: xem trực tiếp ảnh/video/ghi âm hoặc nhấn **Tải**.
  - **Trạng thái xử lý**: chọn trạng thái mới rồi nhấn **Cập nhật** — người gửi sẽ nhận thông báo.
  - **Trao đổi với người gửi**: nhập phản hồi hoặc đề nghị bổ sung thông tin rồi nhấn **Gửi**.
    Chỉ người gửi hồ sơ đó đọc được tin nhắn.

---

## 3. DÀNH CHO QUẢN TRỊ VIÊN (CỔNG WEB)

### 3.1. Đăng nhập
Như mục 2.1, dùng tài khoản Quản trị viên. Trang **Tổng quan** có các **Thao tác nhanh**.

### 3.2. Nhân sự
- Xem danh sách nhân viên, phòng ban, vai trò và trạng thái tài khoản.
- **Thêm nhân viên**: nhập mã nhân viên, họ tên, phòng ban, vai trò, mật khẩu khởi tạo
  (tối thiểu 8 ký tự).
- **Khóa / Mở khóa**: tạm ngưng quyền truy cập khi nhân viên nghỉ việc hoặc mất thiết bị.

### 3.3. Bảng tin (Truyền thông)
- Nhập **Tiêu đề**, **Nội dung**, chọn **Ghim lên đầu bảng tin** nếu cần, nhấn **Đăng thông báo**.
- Xóa bài cũ bằng nút **Xóa**.

> [!IMPORTANT]
> Quản trị viên **không xem được nội dung hồ sơ tố giác** — chỉ thấy số lượng trên trang Tổng quan.

---

## 4. CÂU HỎI THƯỜNG GẶP

| Câu hỏi | Trả lời |
|---|---|
| Công ty có biết tôi là người gửi tố giác không? | Không. Hệ thống chỉ biết có một nhân viên hợp lệ đã gửi, không lưu thông tin cho biết đó là ai. |
| Ứng dụng báo "Không thể kết nối tới máy chủ" | Kiểm tra mạng Wi-Fi / 4G rồi thử lại. Nếu vẫn lỗi, liên hệ bộ phận kỹ thuật. |
| Ứng dụng báo "đã dùng hết số lượt gửi tố giác trong tuần" | Mỗi tuần được gửi tối đa 5 tố giác; vui lòng gửi lại vào tuần sau. |
| Tôi đổi điện thoại, có xem lại tố giác cũ được không? | Không — tố giác chỉ lưu trên máy đã gửi để bảo vệ bạn. |
| Trình duyệt cảnh báo chứng chỉ khi mở cổng web | Liên hệ bộ phận kỹ thuật để cài chứng chỉ của công ty (xem `https-setup.md`). |
