package com.atbm.app.domain.notification

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import com.atbm.app.data.api.NetworkClient
import com.atbm.app.data.db.SecureVaultDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Trình Quản Lý Thông Báo Độc Lập & Cập Nhật Hồ Sơ (Zero-Knowledge In-App & Local Notifications).
 * 
 * NGUYÊN TẮC BẢO MẬT & ZERO-KNOWLEDGE:
 * 1. Không dùng FCM token liên kết hồ sơ trên Server (chống de-anonymize nhân viên tố giác).
 * 2. Tra cứu định kỳ / sự kiện bằng các endpoint ẩn danh không mang Bearer Token hoặc định danh thiết bị.
 * 3. Tự động so sánh số lượng phản hồi và trạng thái thụ lý với bộ đệm SQLCipher.
 * 4. Kích hoạt Local System Notification trên máy người dùng khi có tin nhắn mới hoặc thay đổi trạng thái.
 */
object CaseNotificationManager {

    const val CHANNEL_ID = "atbm_case_notifications"
    private const val CHANNEL_NAME = "Thông Báo Hồ Sơ Tố Giác"
    private const val CHANNEL_DESC = "Cập nhật tiến độ thụ lý và phản hồi điều tra từ Ban Thanh Tra"

    /**
     * Khởi tạo Notification Channel cho Android 8.0+ (API 26+).
     */
    fun initChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val importance = NotificationManager.IMPORTANCE_HIGH
            val channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, importance).apply {
                description = CHANNEL_DESC
                enableVibration(true)
            }
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            manager?.createNotificationChannel(channel)
        }
    }

    /**
     * Bắn Local System Notification khi phát hiện cập nhật mới.
     */
    fun showLocalNotification(
        context: Context,
        title: String,
        message: String,
        notificationId: Int
    ) {
        initChannel(context)
        try {
            val builder = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(message)
                .setStyle(NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)

            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            manager?.notify(notificationId, builder.build())
        } catch (_: Exception) {
            // Bảo vệ không crash nếu quyền bị chặn
        }
    }

    /**
     * Đồng bộ kiểm tra trạng thái toàn bộ hồ sơ trong Secure Vault cục bộ.
     * Trả về tổng số hồ sơ có cập nhật chưa đọc.
     */
    suspend fun checkCaseUpdates(context: Context): Int = withContext(Dispatchers.IO) {
        val vault = SecureVaultDatabase(context)
        val passphrase = "VAULT_MASTER_KEY_SQLCIPHER"
        val cases = try {
            vault.getAllCases(passphrase)
        } catch (_: Exception) {
            emptyList()
        }

        if (cases.isEmpty()) {
            return@withContext 0
        }

        var unreadCount = 0

        for (c in cases) {
            try {
                val resp = NetworkClient.anonymousApi.getCaseStatus(c.caseToken)
                if (resp.isSuccessful && resp.body() != null) {
                    val detail = resp.body()!!
                    val serverMsgCount = detail.messages.size
                    val statusChanged = (detail.status != c.status)
                    val hasNewMessages = (serverMsgCount > c.lastMessageCount)

                    if (statusChanged || hasNewMessages) {
                        vault.updateCaseSync(
                            passphrase = passphrase,
                            caseToken = c.caseToken,
                            newStatus = detail.status,
                            newMessageCount = serverMsgCount,
                            hasNewUpdate = true
                        )

                        val notifTitle = "🛡️ Cập Nhật Hồ Sơ #${c.caseToken.takeLast(6)}"
                        val notifText = when {
                            hasNewMessages && statusChanged ->
                                "Ban Thanh tra đã gửi phản hồi mới và chuyển trạng thái thành '${detail.status}'."
                            hasNewMessages ->
                                "Ban Thanh tra đã gửi tin nhắn phản hồi điều tra mới."
                            else ->
                                "Trạng thái hồ sơ đã chuyển thành '${detail.status}'."
                        }

                        showLocalNotification(
                            context = context,
                            title = notifTitle,
                            message = notifText,
                            notificationId = c.caseToken.hashCode()
                        )
                    }
                }
            } catch (_: Exception) {
                // Tiếp tục kiểm tra các case khác nếu lỗi mạng
            }
        }

        unreadCount = try {
            vault.getUnreadCount(passphrase)
        } catch (_: Exception) {
            0
        }

        unreadCount
    }
}
