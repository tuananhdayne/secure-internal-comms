package com.atbm.app.domain.crypto

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigInteger
import java.security.KeyPairGenerator
import java.security.interfaces.RSAPrivateCrtKey
import java.security.interfaces.RSAPublicKey

class CryptoUnitTest {

    @Test
    fun testRsaBlindSignatureMathRoundtrip() {
        // 1. Giả lập Officer sinh cặp khóa RSA-2048
        val kpg = KeyPairGenerator.getInstance("RSA")
        kpg.initialize(2048)
        val kp = kpg.generateKeyPair()
        val pub = kp.public as RSAPublicKey
        val priv = kp.private as RSAPrivateCrtKey

        val e = pub.publicExponent
        val n = pub.modulus
        val d = priv.privateExponent

        // 2. Client tính H
        val category = "Tham nhũng"
        val encTitle = "Tiêu đề mật"
        val encDesc = "Mô tả mật"
        val caseToken = "CASE-123456"
        val casePubKey = "04112233"
        val fileHashes = listOf("hash_file_a", "hash_file_b")

        val h = RsaBlindClient.computePayloadHash(
            category, encTitle, encDesc, caseToken, casePubKey, fileHashes, n
        )
        assertTrue(h > BigInteger.ONE && h < n)

        // 3. Client làm mù: m* = (H * r^e) mod N
        val blindingResult = RsaBlindClient.blindMessage(h, e, n)
        val mStar = blindingResult.mStar
        val r = blindingResult.r

        // 4. Officer ký mù: s* = (m*)^d mod N
        val sStar = mStar.modPow(d, n)

        // 5. Client bóc mù: s = (s* * r^-1) mod N
        val s = RsaBlindClient.unblindSignature(sStar, r, n)

        // 6. Xác minh tính toàn vẹn toán học: s^e mod N == H
        val isValid = RsaBlindClient.verifySignature(h, s, e, n)
        assertTrue("Chữ ký mù sau khi bóc phải thỏa mãn s^e mod N == H", isValid)

        // Thử nghiệm tráo đổi H giả mạo -> Phải thất bại
        val fakeH = h.add(BigInteger.ONE)
        val isFakeValid = RsaBlindClient.verifySignature(fakeH, s, e, n)
        assertFalse("H giả mạo không được phép khớp với chữ ký s", isFakeValid)
    }

    @Test
    fun testEciesRoundtrip() {
        // Sinh cặp khóa người nhận
        val recipientKeyPair = EciesHelper.generateEcKeyPair()
        val recipientPubHex = EciesHelper.exportPublicKeyToHex(recipientKeyPair.public)
        assertNotNull(recipientPubHex)
        assertEquals(130, recipientPubHex.length) // 65 bytes = 130 hex chars

        val originalPlaintext = "Bí mật nội bộ ATBM KMA 2026 - Không rò rỉ".toByteArray(Charsets.UTF_8)

        // Mã hóa ECIES
        val payload = EciesHelper.eciesEncrypt(recipientPubHex, originalPlaintext)
        assertNotNull(payload.ephemeralPublicKeyHex)
        assertNotNull(payload.ciphertextHex)
        assertNotNull(payload.ivHex)
        assertNotNull(payload.authTagHex)

        // Giải mã ECIES
        val decryptedBytes = EciesHelper.eciesDecrypt(
            recipientPrivateKey = recipientKeyPair.private,
            ephemeralPublicKeyHex = payload.ephemeralPublicKeyHex,
            ivHex = payload.ivHex,
            ciphertextHex = payload.ciphertextHex,
            authTagHex = payload.authTagHex
        )

        val decryptedText = String(decryptedBytes, Charsets.UTF_8)
        assertEquals(String(originalPlaintext, Charsets.UTF_8), decryptedText)
    }

    @Test
    fun testEcdsaMessageSigning() {
        val keyPair = EciesHelper.generateEcKeyPair()
        val message = "Nội dung tin nhắn chat ẩn danh số 1".toByteArray(Charsets.UTF_8)

        val signatureHex = EciesHelper.signMessage(keyPair.private, message)
        assertNotNull(signatureHex)
        assertTrue(signatureHex.isNotEmpty())
    }
}
