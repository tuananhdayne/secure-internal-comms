package com.atbm.app.domain.crypto

import java.math.BigInteger
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Chữ ký mù RSA theo chuẩn RFC 9474 — biến thể RSABSSA-SHA384-PSS-Deterministic (phía app).
 *
 * Luồng: encoded = EMSA-PSS-ENCODE(msg) -> m = OS2IP(encoded) -> blinded = m·r^e mod n (gửi server)
 *        -> server trả s* = blinded^d -> s = s*·r⁻¹ mod n, kiểm tra s^e == m -> gửi s.
 * Server xác minh s là chữ ký RSASSA-PSS (SHA-384, MGF1-SHA384, salt 48 byte) chuẩn của msg.
 *
 * PHẢI khớp từng byte với backend/app/crypto/blind_signature.py — kiểm tra chéo bằng
 * protocol/test_vectors.json (ProtocolVectorsTest). Đặc tả: docs/protocol.md.
 * Server chỉ thấy giá trị đã làm mù nên không thể liên kết chữ ký cuối cùng với nhân viên.
 */
object RsaBlindClient {

    private const val HASH_LEN = 48  // SHA-384
    const val SALT_LEN = 48

    data class BlindingResult(
        val mStar: BigInteger,   // giá trị đã làm mù gửi lên server
        val r: BigInteger,       // hệ số làm mù (bí mật, chỉ giữ trong bộ nhớ)
        val encoded: BigInteger  // m = OS2IP(EMSA-PSS-ENCODE(msg)), dùng để kiểm tra khi bóc mù
    )

    /** Thông điệp được ký mù: các trường (trim, UTF-8) nối bằng '|', mã băm tệp sắp tăng dần. */
    fun payloadMessage(
        category: String,
        encryptedTitle: String,
        encryptedDescription: String,
        caseToken: String,
        casePublicKeyHex: String,
        evidenceFileHashes: List<String>
    ): ByteArray {
        val parts = listOf(category, encryptedTitle, encryptedDescription, caseToken, casePublicKeyHex) +
            evidenceFileHashes.map { it.trim() }.sorted()
        return parts.joinToString("|") { it.trim() }.toByteArray(Charsets.UTF_8)
    }

    private fun sha384(vararg chunks: ByteArray): ByteArray {
        val md = MessageDigest.getInstance("SHA-384")
        chunks.forEach { md.update(it) }
        return md.digest()
    }

    private fun mgf1(seed: ByteArray, length: Int): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        var counter = 0
        while (out.size() < length) {
            val c = byteArrayOf((counter ushr 24).toByte(), (counter ushr 16).toByte(), (counter ushr 8).toByte(), counter.toByte())
            out.write(sha384(seed, c))
            counter++
        }
        return out.toByteArray().copyOf(length)
    }

    /** EMSA-PSS-ENCODE (RFC 8017 §9.1.1), SHA-384 / MGF1-SHA384 / salt 48 byte. */
    fun emsaPssEncode(msg: ByteArray, emBits: Int, salt: ByteArray? = null): ByteArray {
        val emLen = (emBits + 7) / 8
        require(emLen >= HASH_LEN + SALT_LEN + 2) { "Khóa RSA quá ngắn cho PSS-SHA384" }
        val s = salt ?: ByteArray(SALT_LEN).also { SecureRandom().nextBytes(it) }
        require(s.size == SALT_LEN) { "Salt phải dài 48 byte" }
        val mHash = sha384(msg)
        val h = sha384(ByteArray(8), mHash, s)
        val db = ByteArray(emLen - HASH_LEN - 1)
        db[db.size - SALT_LEN - 1] = 0x01
        System.arraycopy(s, 0, db, db.size - SALT_LEN, SALT_LEN)
        val mask = mgf1(h, db.size)
        for (i in db.indices) db[i] = (db[i].toInt() xor mask[i].toInt()).toByte()
        db[0] = (db[0].toInt() and (0xFF ushr (8 * emLen - emBits))).toByte()
        return db + h + byteArrayOf(0xBC.toByte())
    }

    /** Blind (RFC 9474 §4.2). */
    fun blind(
        msg: ByteArray, e: BigInteger, n: BigInteger,
        salt: ByteArray? = null, fixedR: BigInteger? = null
    ): BlindingResult {
        val m = BigInteger(1, emsaPssEncode(msg, n.bitLength() - 1, salt))
        require(m.gcd(n) == BigInteger.ONE) { "Thông điệp không hợp lệ" }
        val random = SecureRandom()
        var r = fixedR
        while (r == null || r <= BigInteger.ONE || r >= n || r.gcd(n) != BigInteger.ONE) {
            r = BigInteger(n.bitLength() - 1, random)
        }
        return BlindingResult(mStar = m.multiply(r.modPow(e, n)).mod(n), r = r, encoded = m)
    }

    /** Finalize (RFC 9474 §4.4): bóc mù rồi KIỂM TRA chữ ký trước khi dùng. */
    fun finalize(sStar: BigInteger, blinding: BlindingResult, e: BigInteger, n: BigInteger): BigInteger {
        val s = sStar.multiply(blinding.r.modInverse(n)).mod(n)
        require(s.modPow(e, n) == blinding.encoded) { "Chữ ký mù trả về không hợp lệ" }
        return s
    }
}
