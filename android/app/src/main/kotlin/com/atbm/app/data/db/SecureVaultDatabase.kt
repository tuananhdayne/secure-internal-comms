package com.atbm.app.data.db

import android.content.ContentValues
import android.content.Context
import net.sqlcipher.database.SQLiteDatabase
import net.sqlcipher.database.SQLiteOpenHelper
import java.io.File
import java.security.SecureRandom

/**
 * Kho Lưu Trữ Bí Mật Cục Bộ Mã Hóa (Secure Vault) trên Android.
 * Sử dụng SQLCipher mã hóa toàn bộ cơ sở dữ liệu ở tầng đĩa (AES-256).
 * 
 * NGUYÊN TẮC AN TOÀN & PANIC PIN:
 * - Lưu trữ Case Token, Case Private Key (ECC P-256), Chữ ký mù đã bóc s.
 * - Hỗ trợ hàm emergencyWipe(): Tiêu hủy toàn bộ dữ liệu bằng ghi đè ngẫu nhiên
 *   (Zeroize / Forensic Shredding) khi người dùng kích hoạt mã khẩn cấp (Panic PIN).
 */
class SecureVaultDatabase(context: Context) : SQLiteOpenHelper(
    context,
    DATABASE_NAME,
    null,
    DATABASE_VERSION
) {

    private val dbFile: File = context.getDatabasePath(DATABASE_NAME)

    init {
        // Nạp native libraries của SQLCipher
        SQLiteDatabase.loadLibs(context)
    }

    companion object {
        private const val DATABASE_NAME = "secure_vault.db"
        private const val DATABASE_VERSION = 1

        const val TABLE_CASES = "vault_cases"
        const val COL_TOKEN = "case_token"
        const val COL_CATEGORY = "category"
        const val COL_TITLE = "title"
        const val COL_PRIV_KEY = "case_private_key_hex"
        const val COL_PUB_KEY = "case_public_key_hex"
        const val COL_SIGNATURE = "unblinded_signature"
        const val COL_STATUS = "status"
        const val COL_CREATED_AT = "created_at"
        const val COL_LAST_MESSAGE_COUNT = "last_message_count"
        const val COL_HAS_UNREAD = "has_unread"
    }

    override fun onCreate(db: SQLiteDatabase) {
        val createSql = """
            CREATE TABLE IF NOT EXISTS $TABLE_CASES (
                $COL_TOKEN TEXT PRIMARY KEY,
                $COL_CATEGORY TEXT NOT NULL,
                $COL_TITLE TEXT NOT NULL,
                $COL_PRIV_KEY TEXT NOT NULL,
                $COL_PUB_KEY TEXT NOT NULL,
                $COL_SIGNATURE TEXT NOT NULL,
                $COL_STATUS TEXT NOT NULL,
                $COL_CREATED_AT TEXT NOT NULL,
                $COL_LAST_MESSAGE_COUNT INTEGER NOT NULL DEFAULT 0,
                $COL_HAS_UNREAD INTEGER NOT NULL DEFAULT 0
            )
        """.trimIndent()
        db.execSQL(createSql)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        ensureColumns(db)
    }

    private fun ensureColumns(db: SQLiteDatabase) {
        try {
            db.execSQL("ALTER TABLE $TABLE_CASES ADD COLUMN $COL_LAST_MESSAGE_COUNT INTEGER NOT NULL DEFAULT 0")
        } catch (_: Exception) {}
        try {
            db.execSQL("ALTER TABLE $TABLE_CASES ADD COLUMN $COL_HAS_UNREAD INTEGER NOT NULL DEFAULT 0")
        } catch (_: Exception) {}
    }

    data class VaultCaseItem(
        val caseToken: String,
        val category: String,
        val title: String,
        val casePrivateKeyHex: String,
        val casePublicKeyHex: String,
        val unblindedSignature: String,
        val status: String,
        val createdAt: String,
        val lastMessageCount: Int = 0,
        val hasUnread: Boolean = false
    )

    /**
     * Thêm hoặc cập nhật hồ sơ vào Secure Vault.
     */
    fun saveCase(passphrase: String, item: VaultCaseItem) {
        val db = getWritableDatabase(passphrase)
        ensureColumns(db)
        val values = ContentValues().apply {
            put(COL_TOKEN, item.caseToken)
            put(COL_CATEGORY, item.category)
            put(COL_TITLE, item.title)
            put(COL_PRIV_KEY, item.casePrivateKeyHex)
            put(COL_PUB_KEY, item.casePublicKeyHex)
            put(COL_SIGNATURE, item.unblindedSignature)
            put(COL_STATUS, item.status)
            put(COL_CREATED_AT, item.createdAt)
            put(COL_LAST_MESSAGE_COUNT, item.lastMessageCount)
            put(COL_HAS_UNREAD, if (item.hasUnread) 1 else 0)
        }
        db.insertWithOnConflict(TABLE_CASES, null, values, SQLiteDatabase.CONFLICT_REPLACE)
        db.close()
    }

    /**
     * Lấy danh sách toàn bộ hồ sơ trong Vault.
     */
    fun getAllCases(passphrase: String): List<VaultCaseItem> {
        val list = mutableListOf<VaultCaseItem>()
        val db = getReadableDatabase(passphrase)
        ensureColumns(db)
        val cursor = db.query(TABLE_CASES, null, null, null, null, null, "$COL_CREATED_AT DESC")

        cursor.use { c ->
            val idxToken = c.getColumnIndexOrThrow(COL_TOKEN)
            val idxCat = c.getColumnIndexOrThrow(COL_CATEGORY)
            val idxTitle = c.getColumnIndexOrThrow(COL_TITLE)
            val idxPriv = c.getColumnIndexOrThrow(COL_PRIV_KEY)
            val idxPub = c.getColumnIndexOrThrow(COL_PUB_KEY)
            val idxSig = c.getColumnIndexOrThrow(COL_SIGNATURE)
            val idxStat = c.getColumnIndexOrThrow(COL_STATUS)
            val idxCreated = c.getColumnIndexOrThrow(COL_CREATED_AT)
            val idxMsgCount = c.getColumnIndex(COL_LAST_MESSAGE_COUNT)
            val idxUnread = c.getColumnIndex(COL_HAS_UNREAD)

            while (c.moveToNext()) {
                val lastMsgCount = if (idxMsgCount != -1) c.getInt(idxMsgCount) else 0
                val hasUnread = if (idxUnread != -1) (c.getInt(idxUnread) == 1) else false

                list.add(
                    VaultCaseItem(
                        caseToken = c.getString(idxToken),
                        category = c.getString(idxCat),
                        title = c.getString(idxTitle),
                        casePrivateKeyHex = c.getString(idxPriv),
                        casePublicKeyHex = c.getString(idxPub),
                        unblindedSignature = c.getString(idxSig),
                        status = c.getString(idxStat),
                        createdAt = c.getString(idxCreated),
                        lastMessageCount = lastMsgCount,
                        hasUnread = hasUnread
                    )
                )
            }
        }
        db.close()
        return list
    }

    /**
     * Cập nhật trạng thái hồ sơ.
     */
    fun updateCaseStatus(passphrase: String, caseToken: String, newStatus: String) {
        val db = getWritableDatabase(passphrase)
        ensureColumns(db)
        val values = ContentValues().apply {
            put(COL_STATUS, newStatus)
        }
        db.update(TABLE_CASES, values, "$COL_TOKEN = ?", arrayOf(caseToken))
        db.close()
    }

    /**
     * Đánh dấu hồ sơ đã đọc và cập nhật số lượng tin nhắn hiện tại.
     */
    fun markCaseAsRead(passphrase: String, caseToken: String, currentMessageCount: Int) {
        val db = getWritableDatabase(passphrase)
        ensureColumns(db)
        val values = ContentValues().apply {
            put(COL_HAS_UNREAD, 0)
            put(COL_LAST_MESSAGE_COUNT, currentMessageCount)
        }
        db.update(TABLE_CASES, values, "$COL_TOKEN = ?", arrayOf(caseToken))
        db.close()
    }

    /**
     * Đồng bộ hồ sơ khi có cập nhật mới từ Ban Thanh tra.
     */
    fun updateCaseSync(
        passphrase: String,
        caseToken: String,
        newStatus: String,
        newMessageCount: Int,
        hasNewUpdate: Boolean
    ) {
        val db = getWritableDatabase(passphrase)
        ensureColumns(db)
        val values = ContentValues().apply {
            put(COL_STATUS, newStatus)
            put(COL_LAST_MESSAGE_COUNT, newMessageCount)
            if (hasNewUpdate) {
                put(COL_HAS_UNREAD, 1)
            }
        }
        db.update(TABLE_CASES, values, "$COL_TOKEN = ?", arrayOf(caseToken))
        db.close()
    }

    /**
     * Đếm tổng số hồ sơ có phản hồi hoặc cập nhật chưa đọc.
     */
    fun getUnreadCount(passphrase: String): Int {
        var count = 0
        val db = getReadableDatabase(passphrase)
        ensureColumns(db)
        try {
            val cursor = db.rawQuery("SELECT COUNT(*) FROM $TABLE_CASES WHERE $COL_HAS_UNREAD = 1", null)
            cursor.use {
                if (it.moveToFirst()) {
                    count = it.getInt(0)
                }
            }
        } catch (_: Exception) {}
        db.close()
        return count
    }

    /**
     * CƠ CHẾ PANIC PIN (DURESS / EMERGENCY WIPE):
     * Khi người dùng nhập mã khẩn cấp (Panic PIN), hệ thống thực hiện:
     * 1. Ghi đè file DB bằng bytes ngẫu nhiên (Forensic Shredding).
     * 2. Xóa hoàn toàn file vật lý khỏi bộ nhớ thiết bị.
     */
    fun emergencyWipe() {
        try {
            close()
            if (dbFile.exists()) {
                val length = dbFile.length()
                val randomBytes = ByteArray(length.toInt())
                SecureRandom().nextBytes(randomBytes)
                dbFile.writeBytes(randomBytes)
                dbFile.delete()
            }
        } catch (_: Exception) {
            // Đảm bảo không bị crash khi khẩn cấp
            dbFile.delete()
        }
    }
}
