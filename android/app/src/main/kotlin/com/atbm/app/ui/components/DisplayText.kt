package com.atbm.app.ui.components

import androidx.compose.ui.graphics.Color
import com.atbm.app.ui.theme.AccentAmber
import com.atbm.app.ui.theme.AccentBlue
import com.atbm.app.ui.theme.AccentGreen
import com.atbm.app.ui.theme.AccentRed
import com.atbm.app.ui.theme.TextSecondary
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/**
 * Chuyển các mã kỹ thuật (trạng thái, vai trò, thời gian ISO, lỗi mạng) sang văn bản
 * thân thiện cho người dùng cuối. Không đưa thuật ngữ kỹ thuật lên giao diện.
 */
object DisplayText {

    data class StatusLabel(val text: String, val color: Color)

    fun caseStatus(status: String?): StatusLabel = when (status?.uppercase()) {
        null, "", "SUBMITTED" -> StatusLabel("Đã gửi", AccentBlue)
        "PENDING", "RECEIVED" -> StatusLabel("Chờ tiếp nhận", AccentAmber)
        "INVESTIGATING", "UNDER_INVESTIGATION" -> StatusLabel("Đang xử lý", AccentBlue)
        "RESOLVED" -> StatusLabel("Đã xử lý xong", AccentGreen)
        "REJECTED" -> StatusLabel("Không chấp nhận", AccentRed)
        else -> StatusLabel("Đang cập nhật", TextSecondary)
    }

    fun role(role: String?): String = when (role?.uppercase()) {
        "SYSTEM_ADMIN" -> "Quản trị viên"
        "COMPLIANCE_OFFICER" -> "Cán bộ Thanh tra"
        "BOARD_DIRECTOR", "BOARD_OF_DIRECTORS" -> "Ban Giám đốc"
        else -> "Nhân viên"
    }

    /** Thời gian từ server (UTC, dạng ISO / "yyyy-MM-dd HH:mm:ss") -> "dd/MM/yyyy HH:mm" giờ máy. */
    fun serverDateTime(raw: String?): String {
        if (raw.isNullOrBlank()) return ""
        val cleaned = raw.replace('T', ' ').substringBefore('.').substringBefore('+').removeSuffix("Z").take(19)
        val patterns = listOf("yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm")
        for (p in patterns) {
            try {
                val parser = SimpleDateFormat(p, Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
                val date = parser.parse(cleaned) ?: continue
                return SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.getDefault()).format(date)
            } catch (_: Exception) {
            }
        }
        return raw.take(16).replace('T', ' ')
    }

    /** Thời gian đã lưu trên máy (giờ địa phương, "yyyy-MM-dd HH:mm:ss") -> "dd/MM/yyyy HH:mm". */
    fun localDateTime(raw: String?): String {
        if (raw.isNullOrBlank()) return ""
        return try {
            val date = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).parse(raw) ?: return raw
            SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.getDefault()).format(date)
        } catch (_: Exception) {
            raw
        }
    }

    /**
     * Mã hồ sơ rút gọn để hiển thị: 6 ký tự chữ/số cuối, viết hoa.
     * "CASE-1731912345678" -> "#345678", "CASE-…9f3a2c" -> "#9F3A2C".
     * Cùng quy tắc với Web Admin (filter Jinja `case_code`, hàm JS `caseCode`).
     */
    fun shortCaseCode(caseToken: String): String =
        "#" + caseToken.filter { it.isLetterOrDigit() }.takeLast(6).uppercase()

    fun networkError(e: Throwable): String = when (e) {
        is java.net.UnknownHostException,
        is java.net.ConnectException,
        is java.net.NoRouteToHostException -> "Không thể kết nối tới máy chủ. Vui lòng kiểm tra kết nối mạng và thử lại."
        is java.net.SocketTimeoutException -> "Máy chủ phản hồi quá lâu. Vui lòng thử lại sau ít phút."
        is javax.net.ssl.SSLException -> "Kết nối không an toàn nên đã bị chặn. Vui lòng liên hệ bộ phận kỹ thuật."
        else -> "Đã xảy ra lỗi. Vui lòng thử lại."
    }
}
