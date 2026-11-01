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
                $COL_CREATED_AT TEXT NOT NULL
            )
        """.trimIndent()
        db.execSQL(createSql)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS $TABLE_CASES")
        onCreate(db)
    }

    data class VaultCaseItem(
        val caseToken: String,
        val category: String,
        val title: String,
        val casePrivateKeyHex: String,
        val casePublicKeyHex: String,
        val unblindedSignature: String,
        val status: String,
        val createdAt: String
    )

    /**
     * Thêm hoặc cập nhật hồ sơ vào Secure Vault.
     */
    fun saveCase(passphrase: String, item: VaultCaseItem) {
        val db = getWritableDatabase(passphrase)
        val values = ContentValues().apply {
            put(COL_TOKEN, item.caseToken)
            put(COL_CATEGORY, item.category)
            put(COL_TITLE, item.title)
            put(COL_PRIV_KEY, item.casePrivateKeyHex)
            put(COL_PUB_KEY, item.casePublicKeyHex)
            put(COL_SIGNATURE, item.unblindedSignature)
            put(COL_STATUS, item.status)
            put(COL_CREATED_AT, item.createdAt)
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

            while (c.moveToNext()) {
                list.add(
                    VaultCaseItem(
                        caseToken = c.getString(idxToken),
                        category = c.getString(idxCat),
                        title = c.getString(idxTitle),
                        casePrivateKeyHex = c.getString(idxPriv),
                        casePublicKeyHex = c.getString(idxPub),
                        unblindedSignature = c.getString(idxSig),
                        status = c.getString(idxStat),
                        createdAt = c.getString(idxCreated)
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
        val values = ContentValues().apply {
            put(COL_STATUS, newStatus)
        }
        db.update(TABLE_CASES, values, "$COL_TOKEN = ?", arrayOf(caseToken))
        db.close()
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
