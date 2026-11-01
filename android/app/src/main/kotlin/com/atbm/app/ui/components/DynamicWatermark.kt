package com.atbm.app.ui.components

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Dynamic Watermark Component (ATBM KMA).
 * 
 * NGUYÊN TẮC BẢO MẬT & TRUY VẾT RÒ RỈ:
 * Vẽ chữ chìm (Watermark) phủ toàn bộ màn hình xem tài liệu nội bộ và tin tức
 * với thông tin định danh của người đang xem và dấu thời gian thực (Timestamp).
 * Nếu người dùng dùng camera ngoài chụp lén màn hình, mã định danh nhân viên
 * sẽ hiện rõ trên bức ảnh rò rỉ, cho phép ban an ninh truy vết thủ phạm 100%.
 */
@Composable
fun DynamicWatermarkBox(
    employeeCode: String,
    fullName: String,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit
) {
    val currentTime = SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault()).format(Date())
    val watermarkText = "ATBM CONFIDENTIAL • $fullName ($employeeCode) • $currentTime"

    Box(modifier = modifier.fillMaxSize()) {
        // 1. Nội dung chính bên dưới
        content()

        // 2. Lớp Watermark phủ bên trên (không cản trở click)
        Canvas(modifier = Modifier.fillMaxSize()) {
            val paint = Paint().apply {
                color = Color.White.copy(alpha = 0.08f).toArgb()
                textSize = 34f
                isAntiAlias = true
                isFakeBoldText = true
            }

            val canvas = drawContext.canvas.nativeCanvas
            val stepY = 220f
            val stepX = 450f

            canvas.save()
            canvas.rotate(-30f, size.width / 2, size.height / 2)

            var y = -size.height
            while (y < size.height * 2) {
                var x = -size.width
                while (x < size.width * 2) {
                    canvas.drawText(watermarkText, x, y, paint)
                    x += stepX
                }
                y += stepY
            }

            canvas.restore()
        }
    }
}
