package com.atbm.app.domain.submission

import android.content.Context
import android.net.Uri
import com.atbm.app.data.api.BlindSignRequest
import com.atbm.app.data.api.NetworkClient
import com.atbm.app.data.db.SecureVaultDatabase
import com.atbm.app.domain.crypto.EciesHelper
import com.atbm.app.domain.crypto.MetadataSanitizer
import com.atbm.app.domain.crypto.RsaBlindClient
import com.atbm.app.ui.components.DisplayText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.math.BigInteger
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/*
 * Luồng gửi tố giác ẩn danh (mật mã + mạng), tách khỏi màn hình giao diện.
 * Đặc tả giao thức: docs/protocol.md. Phải khớp từng byte với server (app/api/v1/anonymous.py).
 */

data class SelectedEvidenceFile(
    val uri: Uri,
    val name: String,
    val size: Long,
    val mimeType: String,
    val typeLabel: String
)

/**
 * Thực thi toàn bộ quy trình mật mã toán học và nộp hồ sơ.
 */
suspend fun executeFullWhistleblowerFlow(
    context: Context,
    token: String,
    category: String,
    title: String,
    description: String,
    attachedFiles: List<SelectedEvidenceFile>,
    onStatus: (String) -> Unit,
    onSuccess: (String) -> Unit
) = withContext(Dispatchers.IO) {
    // Bản sao bằng chứng (đã làm sạch) ghi tạm vào cache để upload: PHẢI xóa sau khi gửi xong,
    // nếu không bằng chứng sẽ nằm lại trên máy người tố giác.
    val tempFiles = mutableListOf<File>()
    try {
        onStatus("Đang chuẩn bị… (1/4)")
        val keysResp = NetworkClient.identifiedApi.getOfficerPublicKeys("Bearer $token")
        if (!keysResp.isSuccessful || keysResp.body() == null) {
            onStatus(if (keysResp.code() == 401) "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại rồi gửi lại." else "Không thể kết nối tới hệ thống. Vui lòng thử lại sau.")
            return@withContext
        }
        val officerKeys = keysResp.body()!!
        val e = BigInteger(officerKeys.blindSignPub.e.removePrefix("0x"), 16)
        val n = BigInteger(officerKeys.blindSignPub.n.removePrefix("0x"), 16)
        val officerChatPubHex = officerKeys.chatPubHex

        onStatus("Đang bảo vệ nội dung… (2/4)")
        val caseKeyPair = EciesHelper.generateEcKeyPair()
        val casePubKeyHex = EciesHelper.exportPublicKeyToHex(caseKeyPair.public)
        val casePrivKeyHex = EciesHelper.exportPrivateKeyToHex(caseKeyPair.private)
        // Mã hồ sơ = bí mật duy nhất để người gửi theo dõi hồ sơ -> 128 bit ngẫu nhiên, không đoán được
        // (trước đây là CASE-<thời điểm ms>, có thể dò ra nếu biết khoảng thời gian gửi).
        val caseToken = "CASE-" + ByteArray(16).also { java.security.SecureRandom().nextBytes(it) }
            .joinToString("") { "%02x".format(it) }

        // Mã hóa ECIES nội dung: title|||description theo format giải mã của Ban Thanh tra
        val fullPayload = "$title|||$description".toByteArray(Charsets.UTF_8)
        val encPayload = EciesHelper.eciesEncrypt(officerChatPubHex, fullPayload)
        val encTitleHex = encPayload.ciphertextHex.take(32)
        val encDescHex = encPayload.ciphertextHex

        // 3. Chuẩn bị các tệp bằng chứng và tính mã băm SHA-256
        onStatus("Đang xử lý tệp đính kèm… (2/4)")
        val evidenceParts = mutableListOf<MultipartBody.Part>()
        val fileHashes = mutableListOf<String>()

        if (attachedFiles.isEmpty()) {
            val dummyEvidence = "ATBM_EVIDENCE_CLEAN_DATA_${System.currentTimeMillis()}".toByteArray(Charsets.UTF_8)
            val fileSha256 = MetadataSanitizer.computeSha256(dummyEvidence)
            fileHashes.add(fileSha256)

            val tempFile = File(context.cacheDir, "evidence_${System.currentTimeMillis()}.bin").apply {
                writeBytes(dummyEvidence)
            }
            tempFiles += tempFile
            val binType = "application/octet-stream".toMediaTypeOrNull()
            evidenceParts.add(
                MultipartBody.Part.createFormData(
                    "files",
                    tempFile.name,
                    tempFile.asRequestBody(binType)
                )
            )
        } else {
            for ((index, fileItem) in attachedFiles.withIndex()) {
                val rawBytes = context.contentResolver.openInputStream(fileItem.uri)?.use { stream ->
                    stream.readBytes()
                } ?: continue

                val isImage = fileItem.mimeType.startsWith("image/") ||
                    fileItem.name.lowercase().endsWith(".jpg") ||
                    fileItem.name.lowercase().endsWith(".jpeg") ||
                    fileItem.name.lowercase().endsWith(".png") ||
                    fileItem.name.lowercase().endsWith(".webp")

                val cleanBytes: ByteArray
                val fHash: String
                if (isImage) {
                    val sanitized = try {
                        MetadataSanitizer.sanitizeImage(rawBytes)
                    } catch (_: Exception) {
                        null
                    }
                    if (sanitized != null) {
                        cleanBytes = sanitized.cleanBytes
                        fHash = sanitized.sha256Hash
                    } else {
                        cleanBytes = rawBytes
                        fHash = MetadataSanitizer.computeSha256(rawBytes)
                    }
                } else {
                    cleanBytes = rawBytes
                    fHash = MetadataSanitizer.computeSha256(rawBytes)
                }

                val safeBaseName = fileItem.name.replace("[^a-zA-Z0-9._-]".toRegex(), "_")
                val tempFile = File(context.cacheDir, "ev_${index}_${System.currentTimeMillis()}_$safeBaseName").apply {
                    writeBytes(cleanBytes)
                }
                tempFiles += tempFile
                fileHashes.add(fHash)

                val mediaType = fileItem.mimeType.toMediaTypeOrNull() ?: "application/octet-stream".toMediaTypeOrNull()
                evidenceParts.add(
                    MultipartBody.Part.createFormData(
                        "files",
                        safeBaseName,
                        tempFile.asRequestBody(mediaType)
                    )
                )
            }
        }

        onStatus("Đang xác nhận quyền gửi… (3/4)")
        // Thông điệp được ký mù theo RFC 9474 (xem docs/protocol.md)
        val message = RsaBlindClient.payloadMessage(
            category = category,
            encryptedTitle = encTitleHex,
            encryptedDescription = encDescHex,
            caseToken = caseToken,
            casePublicKeyHex = casePubKeyHex,
            evidenceFileHashes = fileHashes
        )

        val blinding = RsaBlindClient.blind(message, e, n)
        val mStarHex = "0x" + blinding.mStar.toString(16)  // luôn kèm 0x để server không hiểu nhầm là thập phân

        val blindResp = NetworkClient.identifiedApi.requestBlindSign(
            bearerToken = "Bearer $token",
            req = BlindSignRequest(blindedHash = mStarHex)
        )
        if (!blindResp.isSuccessful || blindResp.body() == null) {
            onStatus(when (blindResp.code()) {
                429, 403 -> "Bạn đã dùng hết số lượt gửi tố giác trong tuần này. Vui lòng thử lại vào tuần sau."
                401 -> "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại rồi gửi lại."
                else -> "Không thể xác nhận quyền gửi lúc này. Vui lòng thử lại sau."
            })
            return@withContext
        }
        val rawSig = blindResp.body()!!.blindSignature.removePrefix("0x").removePrefix("0X")
        val sStar = BigInteger(rawSig, 16)

        val s = try {
            RsaBlindClient.finalize(sStar, blinding, e, n)
        } catch (_: IllegalArgumentException) {
            onStatus("Không thể xác nhận quyền gửi lúc này. Vui lòng thử lại sau.")
            return@withContext
        }
        val sHex = "0x" + s.toString(16)

        // Lưu vào Secure Vault SQLCipher
        val vault = SecureVaultDatabase(context)
        val nowStr = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
        vault.saveCase(
            item = SecureVaultDatabase.VaultCaseItem(
                caseToken = caseToken,
                category = category,
                title = title,
                casePrivateKeyHex = casePrivKeyHex,
                status = "SUBMITTED",
                createdAt = nowStr
            )
        )

        onStatus("Đang gửi tố giác… (4/4)")
        val textType = "text/plain".toMediaTypeOrNull()

        val submitResp = NetworkClient.anonymousApi.submitCase(
            category = category.toRequestBody(textType),
            encryptedTitle = encTitleHex.toRequestBody(textType),
            encryptedDescription = encDescHex.toRequestBody(textType),
            payloadEphemeralPub = encPayload.ephemeralPublicKeyHex.toRequestBody(textType),
            payloadIv = encPayload.ivHex.toRequestBody(textType),
            payloadAuthTag = encPayload.authTagHex.toRequestBody(textType),
            caseToken = caseToken.toRequestBody(textType),
            casePublicKey = casePubKeyHex.toRequestBody(textType),
            unblindedSignature = sHex.toRequestBody(textType),
            files = evidenceParts
        )

        if (submitResp.isSuccessful) {
            onStatus("Đã gửi tố giác thành công.")
            withContext(Dispatchers.Main) {
                onSuccess(caseToken)
            }
        } else {
            onStatus("Gửi tố giác không thành công. Vui lòng thử lại.")
        }
    } catch (e: Exception) {
        onStatus(DisplayText.networkError(e))
    } finally {
        tempFiles.forEach { f ->
            try {
                if (f.exists()) {
                    f.writeBytes(ByteArray(f.length().toInt()))  // ghi đè trước khi xóa
                    f.delete()
                }
            } catch (_: Exception) {
                f.delete()
            }
        }
    }
}
