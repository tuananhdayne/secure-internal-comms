package com.atbm.app.domain.crypto

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.ByteArrayOutputStream
import java.security.MessageDigest

/**
 * Metadata Sanitizer Module (Client Android).
 * 
 * NGUYÊN TẮC BẢO VỆ ẨN DANH:
 * Khi người tố cáo chụp ảnh hiện trường sai phạm, file ảnh gốc thường chứa
 * thẻ EXIF nguy hiểm: Tọa độ định vị GPS (vĩ độ, kinh độ), số serial thiết bị,
 * hãng máy, thời gian chụp chính xác.
 * 
 * Module này giải mã ảnh thành dữ liệu pixel thô (raw bitmap matrix)
 * rồi nén lại thành luồng byte JPEG/PNG hoàn toàn mới, loại bỏ 100% EXIF & GPS
 * trước khi tính mã băm H và gửi lên máy chủ.
 */
object MetadataSanitizer {

    data class SanitizedResult(
        val cleanBytes: ByteArray,
        val sha256Hash: String,
        val width: Int,
        val height: Int
    )

    /**
     * Tẩy sạch toàn bộ siêu dữ liệu ảnh và trả về byte stream sạch kèm mã băm SHA256.
     */
    fun sanitizeImage(imageBytes: ByteArray, quality: Int = 92): SanitizedResult {
        // 1. Giải mã thành Raw Bitmap (chỉ giữ lại điểm ảnh pixel, bỏ toàn bộ EXIF)
        val options = BitmapFactory.Options().apply {
            inPreferredConfig = Bitmap.Config.ARGB_8888
        }
        val bitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size, options)
            ?: throw IllegalArgumentException("Không thể giải mã định dạng ảnh này.")

        // 2. Nén lại thành luồng JPEG mới không kèm thẻ EXIF
        val outputStream = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, quality, outputStream)
        val cleanBytes = outputStream.toByteArray()

        val width = bitmap.width
        val height = bitmap.height
        bitmap.recycle()

        // 3. Tính mã băm toàn vẹn SHA-256
        val md = MessageDigest.getInstance("SHA-256")
        val hashBytes = md.digest(cleanBytes)
        val sha256Hex = hashBytes.joinToString("") { "%02x".format(it) }

        return SanitizedResult(
            cleanBytes = cleanBytes,
            sha256Hash = sha256Hex,
            width = width,
            height = height
        )
    }

    /**
     * Tính mã băm SHA-256 của file bất kỳ (PDF, âm thanh, v.v.).
     */
    fun computeSha256(data: ByteArray): String {
        val md = MessageDigest.getInstance("SHA-256")
        val hashBytes = md.digest(data)
        return hashBytes.joinToString("") { "%02x".format(it) }
    }
}
