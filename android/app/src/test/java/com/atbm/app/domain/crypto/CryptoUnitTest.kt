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

        // 2. App dựng thông điệp cần ký mù
        val msg = RsaBlindClient.payloadMessage(
            "Tham nhũng", "Tiêu đề mật", "Mô tả mật", "CASE-" + "ab".repeat(16), "04112233",
            listOf("hash_file_a", "hash_file_b")
        )

        // 3. App làm mù (RFC 9474 Blind): mã hóa PSS rồi nhân r^e
        val blinding = RsaBlindClient.blind(msg, e, n)
        assertTrue(blinding.mStar > BigInteger.ONE && blinding.mStar < n)

        // 4. Ban Thanh tra ký mù: s* = (m*)^d mod N
        val sStar = blinding.mStar.modPow(d, n)

        // 5. App bóc mù + kiểm tra (RFC 9474 Finalize)
        val s = RsaBlindClient.finalize(sStar, blinding, e, n)

        // 6. Chữ ký cuối là RSASSA-PSS chuẩn: thư viện Java xác minh được
        val verifier = java.security.Signature.getInstance("RSASSA-PSS").apply {
            setParameter(java.security.spec.PSSParameterSpec("SHA-384", "MGF1", java.security.spec.MGF1ParameterSpec.SHA384, 48, 1))
            initVerify(pub)
        }
        val sigBytes = s.toByteArray().let { if (it.size > 256) it.copyOfRange(it.size - 256, it.size) else ByteArray(256 - it.size) + it }
        verifier.update(msg)
        assertTrue("Chữ ký phải là RSA-PSS hợp lệ theo thư viện chuẩn", verifier.verify(sigBytes))

        // 7. Chữ ký mù sai (vd. server trả bừa) phải bị Finalize từ chối
        var rejected = false
        try { RsaBlindClient.finalize(sStar.add(BigInteger.ONE), blinding, e, n) } catch (_: IllegalArgumentException) { rejected = true }
        assertTrue("Finalize phải từ chối chữ ký mù không hợp lệ", rejected)
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

    @Test
    fun testMultimediaFileHashingAndZeroFilesHandling() {
        // Giả lập dữ liệu nhị phân của ảnh, video, âm thanh, tài liệu PDF
        val audioBytes = "RIFF....WAVEfmt....mock_voice_recording".toByteArray(Charsets.UTF_8)
        val videoBytes = "....ftypmp42....mock_security_video".toByteArray(Charsets.UTF_8)
        val docBytes = "%PDF-1.4 mock_confidential_document".toByteArray(Charsets.UTF_8)

        val audioHash = MetadataSanitizer.computeSha256(audioBytes)
        val videoHash = MetadataSanitizer.computeSha256(videoBytes)
        val docHash = MetadataSanitizer.computeSha256(docBytes)

        assertEquals(64, audioHash.length)
        assertEquals(64, videoHash.length)
        assertEquals(64, docHash.length)

        fun msg(hashes: List<String>) = RsaBlindClient.payloadMessage(
            "Gian lận", "enc_title", "enc_desc", "CASE-101", "04abcd", hashes
        ).toString(Charsets.UTF_8)
        val withFiles = msg(listOf(audioHash, videoHash, docHash))
        // Thứ tự danh sách mã băm tệp không làm đổi thông điệp (sorted)
        assertEquals(withFiles, msg(listOf(docHash, audioHash, videoHash)))
        // Không có tệp -> thông điệp khác
        val empty = msg(emptyList())
        assertEquals("Gian lận|enc_title|enc_desc|CASE-101|04abcd", empty)
        assertTrue(withFiles != empty)
    }

    @Test
    fun testVaultCaseItemUnreadState() {
        val itemDefault = com.atbm.app.data.db.SecureVaultDatabase.VaultCaseItem(
            caseToken = "CASE-TEST",
            category = "Tham nhũng",
            title = "Tiêu đề",
            casePrivateKeyHex = "priv",
            casePublicKeyHex = "pub",
            unblindedSignature = "sig",
            status = "PENDING",
            createdAt = "2026-11-12 12:00:00"
        )
        assertEquals(0, itemDefault.lastMessageCount)
        assertFalse(itemDefault.hasUnread)

        val itemUpdated = itemDefault.copy(lastMessageCount = 3, hasUnread = true)
        assertEquals(3, itemUpdated.lastMessageCount)
        assertTrue(itemUpdated.hasUnread)
    }
}
