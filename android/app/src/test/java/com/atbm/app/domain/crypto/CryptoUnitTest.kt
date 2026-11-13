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

        val n = BigInteger("32317006071311007300714876688669951960444102669715484032130345427524655794193")
        val hWithFiles = RsaBlindClient.computePayloadHash(
            category = "Gian lận",
            encryptedTitle = "enc_title",
            encryptedDescription = "enc_desc",
            caseToken = "CASE-101",
            casePublicKeyHex = "04abcd",
            evidenceFileHashes = listOf(audioHash, videoHash, docHash),
            n = n
        )
        assertTrue(hWithFiles > BigInteger.ONE && hWithFiles < n)

        // Kiểm tra thứ tự độc lập (sắp xếp hash tự động)
        val hReversed = RsaBlindClient.computePayloadHash(
            category = "Gian lận",
            encryptedTitle = "enc_title",
            encryptedDescription = "enc_desc",
            caseToken = "CASE-101",
            casePublicKeyHex = "04abcd",
            evidenceFileHashes = listOf(docHash, audioHash, videoHash),
            n = n
        )
        assertEquals("Thứ tự danh sách file hash đưa vào không được làm đổi mã băm H do cơ chế sorted()", hWithFiles, hReversed)

        // Kiểm tra trường hợp 0 file (empty list)
        val hEmpty = RsaBlindClient.computePayloadHash(
            category = "Gian lận",
            encryptedTitle = "enc_title",
            encryptedDescription = "enc_desc",
            caseToken = "CASE-101",
            casePublicKeyHex = "04abcd",
            evidenceFileHashes = emptyList(),
            n = n
        )
        assertTrue(hEmpty > BigInteger.ONE && hEmpty < n)
        assertTrue("H khi có file phải khác H khi không có file", hWithFiles != hEmpty)
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
