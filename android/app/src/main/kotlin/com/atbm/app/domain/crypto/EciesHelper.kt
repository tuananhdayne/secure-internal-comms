package com.atbm.app.domain.crypto

import java.math.BigInteger
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.PrivateKey
import java.security.PublicKey
import java.security.SecureRandom
import java.security.Signature
import java.security.interfaces.ECPrivateKey
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPublicKeySpec
import java.security.spec.PKCS8EncodedKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Bộ công cụ Mật mã học Bất đối xứng ECIES SECP256R1 và Kênh Chat E2EE.
 * Tương thích 100% với backend Python (cryptography ECIES).
 */
object EciesHelper {

    private const val CURVE_NAME = "secp256r1"
    private const val AES_GCM_TAG_LENGTH = 128
    private const val IV_LENGTH_BYTES = 12

    data class EciesPayload(
        val ephemeralPublicKeyHex: String,
        val ivHex: String,
        val ciphertextHex: String,
        val authTagHex: String
    )

    data class AesGcmPayload(
        val ivHex: String,
        val ciphertextHex: String,
        val authTagHex: String
    )

    /**
     * Sinh cặp khóa ECC SECP256R1 mới (ví dụ dùng cho Case Token & Chat E2EE).
     */
    fun generateEcKeyPair(): KeyPair {
        val kpg = KeyPairGenerator.getInstance("EC")
        val ecSpec = ECGenParameterSpec(CURVE_NAME)
        kpg.initialize(ecSpec, SecureRandom())
        return kpg.generateKeyPair()
    }

    /**
     * Xuất Public Key dạng Uncompressed Point Hex (04 || X || Y).
     */
    fun exportPublicKeyToHex(publicKey: PublicKey): String {
        val ecPub = publicKey as ECPublicKey
        val w = ecPub.w
        val xBytes = toFixedByteArray(w.affineX, 32)
        val yBytes = toFixedByteArray(w.affineY, 32)
        val full = ByteArray(65)
        full[0] = 0x04.toByte()
        System.arraycopy(xBytes, 0, full, 1, 32)
        System.arraycopy(yBytes, 0, full, 33, 32)
        return full.toHex()
    }

    /**
     * Xuất Private Key dạng Hex (PKCS#8).
     */
    fun exportPrivateKeyToHex(privateKey: PrivateKey): String {
        return privateKey.encoded.toHex()
    }

    /**
     * Tái tạo Private Key từ PKCS#8 Hex.
     */
    fun importPrivateKeyFromHex(hex: String): PrivateKey {
        val bytes = hex.hexToByteArray()
        val kf = KeyFactory.getInstance("EC")
        return kf.generatePrivate(PKCS8EncodedKeySpec(bytes))
    }

    /**
     * Tái tạo Public Key từ Uncompressed Point Hex (04 || X || Y).
     */
    fun importPublicKeyFromHex(hex: String): PublicKey {
        val bytes = hex.hexToByteArray()
        require(bytes.isNotEmpty() && bytes[0] == 0x04.toByte() && bytes.size == 65) {
            "Định dạng Public Key không hợp lệ (yêu cầu Uncompressed Point 65 bytes)."
        }
        val xBytes = bytes.copyOfRange(1, 33)
        val yBytes = bytes.copyOfRange(33, 65)
        val x = BigInteger(1, xBytes)
        val y = BigInteger(1, yBytes)
        val point = ECPoint(x, y)

        val kf = KeyFactory.getInstance("EC")
        val params = (generateEcKeyPair().public as ECPublicKey).params
        val spec = ECPublicKeySpec(point, params)
        return kf.generatePublic(spec)
    }

    /**
     * Mã hóa dữ liệu bằng ECIES (gửi tới Ban Thanh tra hoặc Người tố cáo):
     * 1. Sinh ephemeral keypair (ephemPriv, ephemPub).
     * 2. ECDH(ephemPriv, recipientPub) -> sharedSecret.
     * 3. HKDF-SHA256(sharedSecret) -> 32 bytes AES Key.
     * 4. AES-256-GCM encrypt.
     */
    fun eciesEncrypt(recipientPublicKeyHex: String, plaintext: ByteArray): EciesPayload {
        val recipientPub = importPublicKeyFromHex(recipientPublicKeyHex)
        val ephemeralKeyPair = generateEcKeyPair()

        // 1. ECDH Key Agreement
        val ka = KeyAgreement.getInstance("ECDH")
        ka.init(ephemeralKeyPair.private)
        ka.doPhase(recipientPub, true)
        val sharedSecret = ka.generateSecret()

        // 2. HKDF-SHA256 sinh AES Key 32 bytes
        val aesKeyBytes = deriveAesKeyHkdf(sharedSecret)

        // 3. AES-256-GCM
        val iv = ByteArray(IV_LENGTH_BYTES)
        SecureRandom().nextBytes(iv)

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val keySpec = SecretKeySpec(aesKeyBytes, "AES")
        val gcmSpec = GCMParameterSpec(AES_GCM_TAG_LENGTH, iv)
        cipher.init(Cipher.ENCRYPT_MODE, keySpec, gcmSpec)

        val cipherWithTag = cipher.doFinal(plaintext)
        val tagLengthBytes = AES_GCM_TAG_LENGTH / 8
        val ciphertextLen = cipherWithTag.size - tagLengthBytes
        val ciphertext = cipherWithTag.copyOfRange(0, ciphertextLen)
        val tag = cipherWithTag.copyOfRange(ciphertextLen, cipherWithTag.size)

        return EciesPayload(
            ephemeralPublicKeyHex = exportPublicKeyToHex(ephemeralKeyPair.public),
            ivHex = iv.toHex(),
            ciphertextHex = ciphertext.toHex(),
            authTagHex = tag.toHex()
        )
    }

    /**
     * Giải mã ECIES:
     */
    fun eciesDecrypt(
        recipientPrivateKey: PrivateKey,
        ephemeralPublicKeyHex: String,
        ivHex: String,
        ciphertextHex: String,
        authTagHex: String
    ): ByteArray {
        val ephemPub = importPublicKeyFromHex(ephemeralPublicKeyHex)

        // 1. ECDH
        val ka = KeyAgreement.getInstance("ECDH")
        ka.init(recipientPrivateKey)
        ka.doPhase(ephemPub, true)
        val sharedSecret = ka.generateSecret()

        // 2. HKDF
        val aesKeyBytes = deriveAesKeyHkdf(sharedSecret)

        // 3. AES-GCM decrypt
        val iv = ivHex.hexToByteArray()
        val ciphertext = ciphertextHex.hexToByteArray()
        val tag = authTagHex.hexToByteArray()

        val cipherWithTag = ByteArray(ciphertext.size + tag.size)
        System.arraycopy(ciphertext, 0, cipherWithTag, 0, ciphertext.size)
        System.arraycopy(tag, 0, cipherWithTag, ciphertext.size, tag.size)

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val keySpec = SecretKeySpec(aesKeyBytes, "AES")
        val gcmSpec = GCMParameterSpec(AES_GCM_TAG_LENGTH, iv)
        cipher.init(Cipher.DECRYPT_MODE, keySpec, gcmSpec)

        return cipher.doFinal(cipherWithTag)
    }

    /**
     * Ký số ECDSA (SHA256withECDSA) chứng thực tin nhắn chat từ người tố cáo.
     */
    fun signMessage(privateKey: PrivateKey, message: ByteArray): String {
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(privateKey)
        signer.update(message)
        return signer.sign().toHex()
    }

    /**
     * HKDF-SHA256 (RFC 5869) sinh 32 bytes AES Key từ Shared Secret.
     */
    private fun deriveAesKeyHkdf(sharedSecret: ByteArray): ByteArray {
        // PRK = HMAC-SHA256(salt=zeros, IKM=sharedSecret)
        val mac = Mac.getInstance("HmacSHA256")
        val salt = ByteArray(32) { 0 }
        mac.init(SecretKeySpec(salt, "HmacSHA256"))
        val prk = mac.doFinal(sharedSecret)

        // OKM = HMAC-SHA256(PRK, info="ATBM_ECIES_P256" || 0x01)
        val info = "ATBM_ECIES_P256".toByteArray(Charsets.UTF_8)
        val infoWithByte = ByteArray(info.size + 1)
        System.arraycopy(info, 0, infoWithByte, 0, info.size)
        infoWithByte[info.size] = 0x01.toByte()

        mac.init(SecretKeySpec(prk, "HmacSHA256"))
        val okm = mac.doFinal(infoWithByte)
        return okm.copyOfRange(0, 32)
    }

    private fun toFixedByteArray(bi: BigInteger, size: Int): ByteArray {
        val raw = bi.toByteArray()
        val result = ByteArray(size)
        if (raw.size >= size) {
            System.arraycopy(raw, raw.size - size, result, 0, size)
        } else {
            System.arraycopy(raw, 0, result, size - raw.size, raw.size)
        }
        return result
    }

    // Tiện ích Extension chuyển đổi Hex
    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }

    private fun String.hexToByteArray(): ByteArray {
        val clean = this.trim().removePrefix("0x")
        val len = clean.length
        val data = ByteArray(len / 2)
        for (i in 0 until len step 2) {
            data[i / 2] = ((Character.digit(clean[i], 16) shl 4) + Character.digit(clean[i + 1], 16)).toByte()
        }
        return data
    }
}
