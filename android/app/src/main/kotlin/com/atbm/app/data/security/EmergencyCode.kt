package com.atbm.app.data.security

import android.content.Context
import android.util.Base64
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * Mã khẩn cấp dùng để xóa nhanh dữ liệu tố giác trên máy.
 *
 * - Người dùng tự đặt (6–8 chữ số). Chỉ lưu băm PBKDF2-HMAC-SHA256 + salt ngẫu nhiên, không lưu mã rõ.
 * - Chưa đặt thì dùng mã mặc định [DEFAULT_CODE] (ghi trong hướng dẫn sử dụng) — khuyến nghị đổi ngay.
 */
object EmergencyCode {
    const val DEFAULT_CODE = "999999"
    private const val PREFS = "atbm_emergency"
    private const val KEY_HASH = "hash"
    private const val KEY_SALT = "salt"
    private const val ITERATIONS = 120_000

    fun isValidFormat(code: String): Boolean = code.length in 6..8 && code.all(Char::isDigit)

    fun isCustom(context: Context): Boolean = prefs(context).contains(KEY_HASH)

    fun matches(context: Context, input: String): Boolean {
        val p = prefs(context)
        val hash = p.getString(KEY_HASH, null)
        val salt = p.getString(KEY_SALT, null)
        if (hash == null || salt == null) return input == DEFAULT_CODE
        val computed = derive(input, Base64.decode(salt, Base64.NO_WRAP))
        return MessageDigest.isEqual(computed, Base64.decode(hash, Base64.NO_WRAP))
    }

    /** Đổi mã: phải nhập đúng mã hiện tại. Trả về false nếu mã hiện tại sai hoặc mã mới sai định dạng. */
    fun change(context: Context, current: String, newCode: String): Boolean {
        if (!matches(context, current) || !isValidFormat(newCode)) return false
        val salt = ByteArray(16).also { SecureRandom().nextBytes(it) }
        prefs(context).edit()
            .putString(KEY_SALT, Base64.encodeToString(salt, Base64.NO_WRAP))
            .putString(KEY_HASH, Base64.encodeToString(derive(newCode, salt), Base64.NO_WRAP))
            .commit()
        return true
    }

    private fun derive(code: String, salt: ByteArray): ByteArray {
        val spec = PBEKeySpec(code.toCharArray(), salt, ITERATIONS, 256)
        return try {
            SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
        } finally {
            spec.clearPassword()
        }
    }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
