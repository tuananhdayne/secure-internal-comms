package com.atbm.app.domain.crypto

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.math.BigInteger
import java.security.Signature

/**
 * Kiểm thử giao thức bằng bộ dữ liệu DÙNG CHUNG với server: protocol/test_vectors.json
 * (sinh bởi backend/scripts/gen_protocol_vectors.py; phía Python: tests/blackbox/test_protocol_vectors.py).
 * Bên nào đổi cách tính H / ECIES / chữ ký mà bên kia không đổi theo -> test này báo lỗi ngay,
 * thay vì người dùng gặp "chữ ký không hợp lệ" khi gửi tố giác.
 */
class ProtocolVectorsTest {

    private val vectors: JsonObject by lazy {
        var dir: File? = File("").absoluteFile
        while (dir != null && !File(dir, "protocol/test_vectors.json").exists()) dir = dir.parentFile
        requireNotNull(dir) { "Không tìm thấy protocol/test_vectors.json" }
        JsonParser.parseString(File(dir, "protocol/test_vectors.json").readText(Charsets.UTF_8)).asJsonObject
    }

    private fun JsonObject.hex(key: String) = BigInteger(get(key).asString, 16)

    private fun hexBytes(hex: String) = ByteArray(hex.length / 2) { i -> hex.substring(2 * i, 2 * i + 2).toInt(16).toByte() }

    @Test
    fun payloadHashMatchesServer() {
        val ph = vectors.getAsJsonObject("payload_hash")
        val n = ph.hex("rsa_n_hex")
        for (el in ph.getAsJsonArray("cases")) {
            val c = el.asJsonObject
            val h = RsaBlindClient.computePayloadHash(
                category = c.get("category").asString,
                encryptedTitle = c.get("encrypted_title").asString,
                encryptedDescription = c.get("encrypted_description").asString,
                caseToken = c.get("case_token").asString,
                casePublicKeyHex = c.get("case_public_key").asString,
                evidenceFileHashes = c.getAsJsonArray("evidence_file_hashes").map { it.asString },
                n = n
            )
            assertEquals("H lệch ở trường hợp: ${c.get("name").asString}", c.get("expected_h_hex").asString, h.toString(16))
        }
    }

    @Test
    fun blindSignatureUnblindMatchesServer() {
        val v = vectors.getAsJsonObject("blind_signature")
        val n = v.hex("n_hex"); val e = v.hex("e_hex"); val r = v.hex("r_hex")
        assertEquals(v.hex("m_star_hex"), v.hex("h_hex").multiply(r.modPow(e, n)).mod(n))
        val s = RsaBlindClient.unblindSignature(v.hex("s_star_hex"), r, n)
        assertEquals(v.hex("s_hex"), s)
        assertTrue(RsaBlindClient.verifySignature(v.hex("h_hex"), s, e, n))
    }

    @Test
    fun eciesFromServerDecryptsOnApp() {
        val ev = vectors.getAsJsonObject("ecies")
        val priv = EciesHelper.importPrivateKeyFromHex(ev.get("recipient_private_pkcs8_hex").asString)
        for (el in ev.getAsJsonArray("cases")) {
            val c = el.asJsonObject
            val plain = EciesHelper.eciesDecrypt(
                recipientPrivateKey = priv,
                ephemeralPublicKeyHex = c.get("ephemeral_public_key").asString,
                ivHex = c.get("iv").asString,
                ciphertextHex = c.get("ciphertext").asString,
                authTagHex = c.get("auth_tag").asString
            )
            assertEquals(c.get("plaintext_utf8").asString, String(plain, Charsets.UTF_8))
        }
    }

    @Test
    fun eciesFromAppRoundTripsWithSameKey() {
        // Mã hóa trên app tới khóa công khai trong vector rồi giải mã lại (cùng tham số HKDF/AES-GCM)
        val ev = vectors.getAsJsonObject("ecies")
        val enc = EciesHelper.eciesEncrypt(ev.get("recipient_public_hex").asString, "Xin chào".toByteArray(Charsets.UTF_8))
        val priv = EciesHelper.importPrivateKeyFromHex(ev.get("recipient_private_pkcs8_hex").asString)
        val plain = EciesHelper.eciesDecrypt(priv, enc.ephemeralPublicKeyHex, enc.ivHex, enc.ciphertextHex, enc.authTagHex)
        assertEquals("Xin chào", String(plain, Charsets.UTF_8))
    }

    @Test
    fun ecdsaSignatureFormatMatchesServer() {
        val v = vectors.getAsJsonObject("ecdsa")
        val pub = EciesHelper.importPublicKeyFromHex(v.get("public_hex").asString)
        val msg = v.get("message_utf8").asString.toByteArray(Charsets.UTF_8)
        // Chữ ký do Python tạo phải verify được trên app (cùng SHA256withECDSA, DER)
        val verifier = Signature.getInstance("SHA256withECDSA").apply { initVerify(pub); update(msg) }
        assertTrue(verifier.verify(hexBytes(v.get("signature_der_hex").asString)))
        // Chữ ký do app tạo cũng đúng định dạng đó
        val priv = EciesHelper.importPrivateKeyFromHex(v.get("private_pkcs8_hex").asString)
        val sigHex = EciesHelper.signMessage(priv, msg)
        val v2 = Signature.getInstance("SHA256withECDSA").apply { initVerify(pub); update(msg) }
        assertTrue(v2.verify(hexBytes(sigHex)))
    }
}
