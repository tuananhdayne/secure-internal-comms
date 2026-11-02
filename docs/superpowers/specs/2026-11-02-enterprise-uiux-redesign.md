# Tài Liệu Thiết Kế: Nâng Cấp Giao Diện Doanh Nghiệp (Enterprise Modernist UI/UX Redesign)

- **Dự án:** Secure Internal Communications & Whistleblower Engine (ATBM)
- **Ngày lập:** 02/11/2026
- **Trạng thái:** Chờ phê duyệt (Pending Approval)

---

## 1. Mục Đích & Bối Cảnh (Intent & The Why)
Giao diện hiện tại của cả Ứng dụng Android (Jetpack Compose) và Cổng thông tin Web (Jinja2 Templates) đã hoàn thiện đầy đủ về logic mật mã và tính năng bảo mật, nhưng mặt thị giác còn mang tính thô sơ, màu sắc cơ bản và thiếu tính chuyên nghiệp.
Mục tiêu của đợt nâng cấp này là **chuyển đổi toàn diện giao diện sang Phong cách Doanh nghiệp Hiện đại (Enterprise Clean & Minimal)** — lấy cảm hứng từ ngôn ngữ thiết kế của **Stripe, Linear và Apple**:
- Tạo ấn tượng sang trọng, cao cấp, chỉn chu ngay từ cái nhìn đầu tiên.
- Tối ưu hóa phân cấp thị giác (Visual Hierarchy), khoảng cách thở (Breathing Space), và tính tương tác mượt mà.
- Làm nổi bật các thành phần bảo mật cốt lõi (Watermark ma trận chìm trang nhã, quy trình ký mù RSA 3 bước, giải mã ECIES trực quan).

---

## 2. Mục Tiêu (Goals, Non-goals & Anti-goals)

### Mục tiêu chính (Goals):
1. **Thiết kế Web Frontend:**
   - Xây dựng hệ thống CSS Design System hoàn chỉnh: Font Inter/SF Pro, bảng màu Dark Slate đa tầng (`#0B0F19`, `#111827`, `#1E293B`, `#334155`), điểm nhấn Royal Blue (`#2563EB`) và Emerald Status (`#10B981`).
   - Cấu trúc giao diện 2 cột: Collapsible Sidebar bên trái với icon SVG tinh gọn + Topbar tích hợp Breadcrumb & User Profile.
   - Thẻ thống kê (Metric Cards): Hiển thị chỉ số to rõ, có icon tương ứng và chỉ báo xu hướng.
   - Bảng dữ liệu (Data Tables): Hairline borders, hover row highlight, thanh tìm kiếm tức thời và bộ lọc trạng thái.
   - Bổ sung màn hình Cán bộ Thanh tra (`/admin/cases`): Hiển thị danh sách hồ sơ tố giác ẩn danh, nút "Giải mã ECIES" kèm chỉ báo toàn vẹn chữ ký mù.
2. **Thiết kế Mobile App Android (Jetpack Compose):**
   - Theme `Theme.kt`: Định nghĩa bảng màu Enterprise Slate & Royal Accent cao cấp, typography phân tầng chuẩn TypeScale Material 3.
   - `LoginScreen.kt`: Form đăng nhập thanh lịch, logo biểu tượng khiên bảo mật tinh tế, trường nhập liệu bo góc mượt mà.
   - `NewsfeedScreen.kt`: Thẻ bài viết dạng Elevated Card với Avatar tác giả, badge phòng ban, thời gian đọc, lớp Watermark chìm alpha 0.05 cực kỳ trang nhã.
   - `WhistleblowerScreen.kt`: Stepper Wizard 3 bước rõ ràng (1. Soạn thảo -> 2. Ký mù RSA -> 3. Mã hóa ECIES & Nộp).
   - `VaultScreen.kt`: Danh sách hồ sơ dạng timeline, trạng thái thẻ màu dịu mắt, nút kích hoạt Panic PIN an toàn.

### Non-goals:
- Không thay đổi bất kỳ logic mật mã học, công thức băm hay quy trình bảo mật nền tảng (RSA-2048, ECIES P-256, SQLite WAL).
- Không chuyển đổi sang Single Page App React/Vue phức tạp để bảo đảm tính độc lập và khả năng chạy offline 100%.

### Anti-goals:
- Tránh phong cách màu mè, neon chói lóa rẻ tiền.
- Không sử dụng các thành phần giao diện quá nặng làm chậm thời gian render trên thiết bị di động.

---

## 3. Các Phương Án Đã Cân Nhắc (Approaches)

| Tiêu chí | Phương Án 1: Enterprise Modernist (Được chọn) | Phương Án 2: SPA React + Vite |
| :--- | :--- | :--- |
| **Kiến trúc** | Tích hợp trực tiếp Jinja2 + CSS Tokens cao cấp + Compose M3 | Tách riêng React App cổng 3000 + Node dependencies |
| **Thẩm mỹ** | Đẳng cấp Stripe/Linear, liền mạch, tải tức thì | Hiện đại nhưng tốn tài nguyên build bundle |
| **Độ phức tạp chạy** | Cực kỳ đơn giản: 1 lệnh Python chạy trọn gói | Phải chạy đồng thời 2 tiến trình (FastAPI + Vite) |
| **Đánh giá** | **Khuyến nghị & Được người dùng chọn** | Bị loại do làm phức tạp hóa môi trường |

---

## 4. Chi Tiết Thiết Kế Kỹ Thuật (Detailed Technical Design)

### 4.1. Hệ Thống Web Frontend (`backend/app/templates/`)
- `base.html`:
  - Khai báo CSS Tokens: `--bg-canvas: #090D16`, `--bg-surface: #111827`, `--bg-elevated: #1F2937`, `--border-subtle: #374151`, `--text-primary: #F9FAFB`, `--text-secondary: #9CA3AF`, `--accent-primary: #3B82F6`, `--accent-success: #10B981`.
  - Sidebar layout: Brand Header -> Navigation Links (Dashboard, Quản lý Nhân sự, Bảng tin Nội bộ, Hồ sơ Thanh tra) -> User Footer.
- `login.html`: Card đăng nhập trung tâm với hiệu ứng viền mờ cao cấp, badge định danh an toàn.
- `dashboard.html`: Grid 4 thẻ thống kê trực quan + Bảng thông báo bài viết mới nhất + Bảng tóm tắt hồ sơ tố giác.
- `users.html`: Bảng nhân sự chuyên nghiệp, modal tạo nhân viên mới dạng floating dialog.
- `posts.html`: Danh sách thông báo dạng feed quản trị, form đăng bài có toggle Ghim ưu tiên.
- `cases.html` (Mới): Trang điều tra của Thanh tra, cho phép bấm nút xem chi tiết và giải mã nội dung ECIES.

### 4.2. Hệ Thống Android Compose (`android/app/src/main/kotlin/com/atbm/app/`)
- `Theme.kt`: Bộ màu Slate Dark (`0xFF0B0F19`, `0xFF161F30`, `0xFF22304A`), Accent Blue (`0xFF2563EB`), Accent Cyan (`0xFF06B6D4`), Success Green (`0xFF10B981`).
- `DynamicWatermark.kt`: Cải tiến ma trận watermark với alpha 0.05, góc nghiêng 25 độ, font chữ mảnh không gây che lấp chữ đọc.
- `LoginScreen.kt`: Thẻ card bo góc 20dp, bóng đổ tinh tế, các input có icon tiền tố rõ ràng.
- `NewsfeedScreen.kt`: Danh sách bài viết mượt mà, hỗ trợ pull-to-refresh và dialog bình luận kiểu bottom sheet.
- `WhistleblowerScreen.kt`: Trực quan hóa quy trình ký mù Chaum bằng các bước minh bạch.
