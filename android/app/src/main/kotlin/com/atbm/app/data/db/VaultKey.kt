package com.atbm.app.data.db

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Khóa mở kho dữ liệu (SQLCipher) RIÊNG CHO TỪNG THIẾT BỊ.
 *
 * - Passphrase = 32 byte ngẫu nhiên (SecureRandom), sinh một lần cho mỗi cài đặt.
 * - Passphrase được bọc bằng khóa AES-256-GCM nằm trong Android Keystore (không trích xuất được
 *   khỏi phần cứng bảo mật); chỉ bản đã bọc + IV được lưu trong SharedPreferences.
 * - [destroy] xóa cả khóa Keystore lẫn bản bọc → dữ liệu kho không thể giải mã dù còn bản sao file
 *   (crypto-shredding, dùng cho chức năng xóa nhanh dữ liệu).
 *
 * Thay cho passphrase cố định "VAULT_MASTER_KEY_SQLCIPHER" trước đây (giống nhau trên mọi máy).
 */
object VaultKey {
    /** Passphrase cố định của các bản cài cũ — CHỈ dùng để chuyển đổi dữ liệu cũ sang khóa mới. */
    internal const val LEGACY_PASSPHRASE = "VAULT_MASTER_KEY_SQLCIPHER"

    private const val KEYSTORE = "AndroidKeyStore"
    private const val KEK_ALIAS = "atbm_vault_kek"
    private const val PREFS = "atbm_vault_key"
    private const val PREF_WRAPPED = "wrapped"
    private const val PREF_IV = "iv"
    private const val GCM_TAG_BITS = 128

    @Volatile private var cached: String? = null

    /** true nếu thiết bị đã có khóa kho riêng (đã chuyển đổi hoặc cài mới). */
    fun exists(context: Context): Boolean =
        prefs(context).contains(PREF_WRAPPED) && keyStore().containsAlias(KEK_ALIAS)

    /** Lấy passphrase hiện có, hoặc sinh mới nếu chưa có. */
    @Synchronized
    fun passphrase(context: Context): String {
        cached?.let { return it }
        val p = prefs(context)
        val wrapped = p.getString(PREF_WRAPPED, null)
        val iv = p.getString(PREF_IV, null)
        val value = if (wrapped != null && iv != null && keyStore().containsAlias(KEK_ALIAS)) {
            unwrap(Base64.decode(wrapped, Base64.NO_WRAP), Base64.decode(iv, Base64.NO_WRAP))
        } else {
            create(context)
        }
        cached = value
        return value
    }

    /** Xóa vĩnh viễn khóa kho (khóa Keystore + bản bọc). */
    @Synchronized
    fun destroy(context: Context) {
        cached = null
        prefs(context).edit().clear().commit()
        try {
            keyStore().deleteEntry(KEK_ALIAS)
        } catch (_: Exception) {
        }
    }

    private fun create(context: Context): String {
        val raw = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val passphrase = raw.joinToString("") { "%02x".format(it) }
        raw.fill(0)
        val kek = generateKek()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, kek) }
        val wrapped = cipher.doFinal(passphrase.toByteArray(Charsets.UTF_8))
        prefs(context).edit()
            .putString(PREF_WRAPPED, Base64.encodeToString(wrapped, Base64.NO_WRAP))
            .putString(PREF_IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .commit()
        return passphrase
    }

    private fun unwrap(wrapped: ByteArray, iv: ByteArray): String {
        val kek = keyStore().getKey(KEK_ALIAS, null) as SecretKey
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, kek, GCMParameterSpec(GCM_TAG_BITS, iv))
        }
        return String(cipher.doFinal(wrapped), Charsets.UTF_8)
    }

    private fun generateKek(): SecretKey {
        val ks = keyStore()
        if (ks.containsAlias(KEK_ALIAS)) ks.deleteEntry(KEK_ALIAS)
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        gen.init(
            KeyGenParameterSpec.Builder(KEK_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return gen.generateKey()
    }

    private fun keyStore(): KeyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
