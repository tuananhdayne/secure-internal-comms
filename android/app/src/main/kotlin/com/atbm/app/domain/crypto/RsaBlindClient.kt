package com.atbm.app.domain.crypto

import java.math.BigInteger
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Động cơ Ký mù RSA của David Chaum trên Android (RSA Blind Signature Client).
 * 
 * NGUYÊN TẮC BẢO MẬT & UNLINKABILITY:
 * - Triển khai bằng Pure BigInteger của Java/Kotlin, tuyệt đối không phụ thuộc thư viện ngoài.
 * - Client tự sinh số ngẫu nhiên bí mật r (Blinding Factor) và làm mù thông điệp H thành m*.
 * - Khi Ban Thanh tra ký mù s* = (m*)^d mod N, họ hoàn toàn KHÔNG THỂ biết nội dung H bên dưới.
 * - Client tự bóc mù để nhận chữ ký s = (s* * r^-1) mod N.
 */
object RsaBlindClient {

    data class BlindingResult(
        val mStar: BigInteger,
        val r: BigInteger
    )

    /**
     * Tính toán mã băm toán học H ràng buộc toàn vẹn giữa nội dung và các tệp đính kèm:
     * H = SHA256(Category | EncTitle | EncDesc | CaseToken | CasePubKey | Hash(File_1) | ... ) mod N
     */
    fun computePayloadHash(
        category: String,
        encryptedTitle: String,
        encryptedDescription: String,
        caseToken: String,
        casePublicKeyHex: String,
        evidenceFileHashes: List<String>,
        n: BigInteger
    ): BigInteger {
        val md = MessageDigest.getInstance("SHA-256")
        
        md.update(category.trim().toByteArray(Charsets.UTF_8))
        md.update("|".toByteArray(Charsets.UTF_8))
        md.update(encryptedTitle.trim().toByteArray(Charsets.UTF_8))
        md.update("|".toByteArray(Charsets.UTF_8))
        md.update(encryptedDescription.trim().toByteArray(Charsets.UTF_8))
        md.update("|".toByteArray(Charsets.UTF_8))
        md.update(caseToken.trim().toByteArray(Charsets.UTF_8))
        md.update("|".toByteArray(Charsets.UTF_8))
        md.update(casePublicKeyHex.trim().toByteArray(Charsets.UTF_8))

        // Sắp xếp tăng dần danh sách mã băm file bằng chứng
        for (fHash in evidenceFileHashes.sorted()) {
            md.update("|".toByteArray(Charsets.UTF_8))
            md.update(fHash.trim().toByteArray(Charsets.UTF_8))
        }

        val digest = md.digest()
        // Chuyển sang BigInteger dương (signum = 1)
        val hInt = BigInteger(1, digest)
        return hInt.mod(n)
    }

    /**
     * Làm mù thông điệp:
     * Chọn r ngẫu nhiên trong [2, N-1] sao cho gcd(r, N) == 1
     * Tính m* = (H * r^e) mod N
     */
    fun blindMessage(h: BigInteger, e: BigInteger, n: BigInteger): BlindingResult {
        val random = SecureRandom()
        val bitLength = n.bitLength() - 1
        var r: BigInteger

        while (true) {
            r = BigInteger(bitLength, random)
            if (r > BigInteger.ONE && r < n && r.gcd(n) == BigInteger.ONE) {
                break
            }
        }

        // r^e mod N
        val rPowE = r.modPow(e, n)
        // m* = (H * rPowE) mod N
        val mStar = (h.multiply(rPowE)).mod(n)

        return BlindingResult(mStar = mStar, r = r)
    }

    /**
     * Bóc mù để thu hồi chữ ký số gốc:
     * s = (s* * r^-1) mod N
     */
    fun unblindSignature(sStar: BigInteger, r: BigInteger, n: BigInteger): BigInteger {
        // r^-1 mod N
        val rInv = r.modInverse(n)
        // s = (s* * rInv) mod N
        return (sStar.multiply(rInv)).mod(n)
    }

    /**
     * Xác minh kiểm tra cục bộ tính hợp lệ của chữ ký mù:
     * s^e mod N == H
     */
    fun verifySignature(h: BigInteger, s: BigInteger, e: BigInteger, n: BigInteger): Boolean {
        if (s <= BigInteger.ONE || s >= n) return false
        val recoveredH = s.modPow(e, n)
        return recoveredH == h
    }
}
