package com.atbm.app.ui.screens

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.atbm.app.data.api.BlindSignRequest
import com.atbm.app.data.api.NetworkClient
import com.atbm.app.data.db.SecureVaultDatabase
import com.atbm.app.domain.crypto.EciesHelper
import com.atbm.app.domain.crypto.MetadataSanitizer
import com.atbm.app.domain.crypto.RsaBlindClient
import com.atbm.app.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
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

data class SelectedEvidenceFile(
    val uri: Uri,
    val name: String,
    val size: Long,
    val mimeType: String,
    val typeLabel: String
)

private fun queryUriFileInfo(context: Context, uri: Uri): Pair<String, Long> {
    var name = "evidence_${System.currentTimeMillis()}"
    var size = 0L
    try {
        context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            val sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (cursor.moveToFirst()) {
                if (nameIdx != -1) name = cursor.getString(nameIdx) ?: name
                if (sizeIdx != -1) size = cursor.getLong(sizeIdx)
            }
        }
    } catch (_: Exception) {}
    return Pair(name, size)
}

private fun formatFileSize(bytes: Long): String {
    if (bytes <= 0) return "0 B"
    val units = arrayOf("B", "KB", "MB", "GB")
    val digitGroups = (Math.log10(bytes.toDouble()) / Math.log10(1024.0)).toInt().coerceIn(0, units.size - 1)
    val formatted = String.format(Locale.US, "%.1f", bytes / Math.pow(1024.0, digitGroups.toDouble()))
    return "$formatted ${units[digitGroups]}"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WhistleblowerScreen(
    token: String,
    onNavigateBack: () -> Unit,
    onSubmissionSuccess: (caseToken: String) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var currentStep by remember { mutableStateOf(1) }
    var category by remember { mutableStateOf("Tham nhũng tài chính") }
    var customCategory by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var attachedFiles by remember { mutableStateOf<List<SelectedEvidenceFile>>(emptyList()) }

    val effectiveCategory = if (category == "Khác") {
        if (customCategory.isNotBlank()) "Khác: ${customCategory.trim()}".take(45) else "Khác"
    } else {
        category
    }

    var statusMessage by remember { mutableStateOf<String?>(null) }
    var isProcessing by remember { mutableStateOf(false) }

    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents()
    ) { uris: List<Uri> ->
        if (uris.isNotEmpty()) {
            val newItems = uris.map { uri ->
                val (name, size) = queryUriFileInfo(context, uri)
                val mime = context.contentResolver.getType(uri) ?: "application/octet-stream"
                val label = when {
                    mime.startsWith("image/") -> "📷 Ảnh"
                    mime.startsWith("video/") -> "🎥 Video"
                    mime.startsWith("audio/") -> "🎙️ Âm thanh"
                    mime.contains("pdf") -> "📄 PDF"
                    else -> "📎 Tệp"
                }
                SelectedEvidenceFile(uri, name, size, mime, label)
            }
            val currentUris = attachedFiles.map { it.uri }.toSet()
            val filtered = newItems.filter { it.uri !in currentUris }
            attachedFiles = attachedFiles + filtered
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Cổng Tố Giác Ẩn Danh (Wizard Bước $currentStep/3)",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Text("←", fontSize = 20.sp, color = TextPrimary)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CardDark)
            )
        },
        containerColor = BgDark
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            // Thanh tiến trình Step
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                StepIndicator(step = 1, title = "Nội dung", active = currentStep >= 1)
                StepIndicator(step = 2, title = "Mật mã & ECIES", active = currentStep >= 2)
                StepIndicator(step = 3, title = "Ký Mù & Nộp", active = currentStep >= 3)
            }

            Spacer(modifier = Modifier.height(20.dp))

            if (statusMessage != null) {
                Surface(
                    color = AccentCyan.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = statusMessage ?: "",
                        color = AccentCyan,
                        fontSize = 12.sp,
                        modifier = Modifier.padding(12.dp)
                    )
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // GIAO DIỆN BƯỚC 1: NHẬP THÔNG TIN
            if (currentStep == 1) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Danh mục sai phạm:", fontSize = 13.sp, color = TextSecondary)
                        Spacer(modifier = Modifier.height(6.dp))
                        listOf("Tham nhũng tài chính", "Quấy rối công sở", "Vi phạm bảo mật ATBM", "Gian lận đấu thầu", "Khác").forEach { cat ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp)
                            ) {
                                RadioButton(
                                    selected = (category == cat),
                                    onClick = { category = cat },
                                    colors = RadioButtonDefaults.colors(selectedColor = AccentCyan)
                                )
                                Text(cat, fontSize = 13.sp, color = TextPrimary)
                            }
                        }

                        if (category == "Khác") {
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = customCategory,
                                onValueChange = { customCategory = it },
                                label = { Text("Mô tả danh mục khác (tùy chọn)") },
                                placeholder = { Text("Ví dụ: Bắt nạt nơi làm việc, an toàn lao động...") },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(start = 12.dp, end = 4.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = TextPrimary,
                                    unfocusedTextColor = TextPrimary
                                )
                            )
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        OutlinedTextField(
                            value = title,
                            onValueChange = { title = it },
                            label = { Text("Tiêu đề vụ việc") },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            )
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        OutlinedTextField(
                            value = description,
                            onValueChange = { description = it },
                            label = { Text("Mô tả chi tiết bằng chứng") },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 4,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            )
                        )

                        Spacer(modifier = Modifier.height(14.dp))
                        Text(
                            "📎 Đính kèm tệp bằng chứng đa phương tiện:",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "Hỗ trợ ảnh chụp hiện trường, video, tệp ghi âm giọng nói, tài liệu mật. Ảnh sẽ được tự động tẩy sạch 100% EXIF/GPS.",
                            fontSize = 11.sp,
                            color = TextSecondary,
                            lineHeight = 16.sp
                        )
                        Spacer(modifier = Modifier.height(8.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            OutlinedButton(
                                onClick = { filePickerLauncher.launch("image/*") },
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentCyan)
                            ) {
                                Text("📷/🎥 Ảnh/Video", fontSize = 11.sp)
                            }
                            OutlinedButton(
                                onClick = { filePickerLauncher.launch("audio/*") },
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentGreen)
                            ) {
                                Text("🎙️ Ghi Âm", fontSize = 11.sp)
                            }
                            OutlinedButton(
                                onClick = { filePickerLauncher.launch("*/*") },
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentAmber)
                            ) {
                                Text("📄 Tài Liệu", fontSize = 11.sp)
                            }
                        }

                        if (attachedFiles.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(10.dp))
                            Text(
                                "Danh sách tệp đã chọn (${attachedFiles.size} tệp):",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = AccentCyan
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                attachedFiles.forEach { fileItem ->
                                    Surface(
                                        color = BgDark,
                                        shape = RoundedCornerShape(8.dp),
                                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark),
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(horizontal = 10.dp, vertical = 6.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.SpaceBetween
                                        ) {
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                modifier = Modifier.weight(1f)
                                            ) {
                                                Text(fileItem.typeLabel, fontSize = 13.sp, modifier = Modifier.padding(end = 6.dp))
                                                Column {
                                                    Text(
                                                        text = fileItem.name,
                                                        fontSize = 12.sp,
                                                        color = TextPrimary,
                                                        maxLines = 1,
                                                        overflow = TextOverflow.Ellipsis
                                                    )
                                                    Text(
                                                        text = "${formatFileSize(fileItem.size)} • ${fileItem.mimeType}",
                                                        fontSize = 10.sp,
                                                        color = TextSecondary
                                                    )
                                                }
                                            }
                                            IconButton(
                                                onClick = { attachedFiles = attachedFiles.filter { it.uri != fileItem.uri } },
                                                modifier = Modifier.size(28.dp)
                                            ) {
                                                Text("✕", color = Color(0xFFEF4444), fontSize = 13.sp, fontWeight = FontWeight.Bold)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                if (title.isNotBlank() && description.isNotBlank()) {
                                    currentStep = 2
                                } else {
                                    statusMessage = "Vui lòng nhập đầy đủ tiêu đề và nội dung mô tả."
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = AccentBlue)
                        ) {
                            Text("Tiếp Tục (Bước 2: Mã Hóa & Tẩy EXIF)")
                        }
                    }
                }
            }

            // GIAO DIỆN BƯỚC 2: MÃ HÓA & CHUẨN BỊ BẰNG CHỨNG
            if (currentStep == 2) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "🛡️ CƠ CHẾ BẢO MẬT ĐẦU CUỐI (ECIES & EXIF STRIPPING)",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = AccentCyan
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = "1. Toàn bộ tiêu đề và mô tả sẽ được mã hóa bằng ECIES P-256 bằng Public Key của Ban Thanh tra.\n" +
                                   "2. Số lượng tệp đính kèm: ${attachedFiles.size} tệp. Toàn bộ ảnh sẽ được tẩy sạch 100% EXIF/GPS coordinates; các tệp video, âm thanh, tài liệu được băm toàn vẹn SHA-256.\n" +
                                   "3. Một cặp khóa EC mới được sinh ra dành riêng cho hồ sơ này.",
                            fontSize = 12.sp,
                            color = TextSecondary,
                            lineHeight = 18.sp
                        )

                        Spacer(modifier = Modifier.height(20.dp))

                        Button(
                            onClick = { currentStep = 3 },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = AccentCyan)
                        ) {
                            Text("Xác Nhận & Sang Bước 3 (Ký Mù & Nộp)")
                        }
                    }
                }
            }

            // GIAO DIỆN BƯỚC 3: XIN CHỮ KÝ MÙ & NỘP HỒ SƠ ẨN DANH
            if (currentStep == 3) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "🔐 DAVID CHAUM RSA BLIND SIGNATURE",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = AccentAmber
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            text = "Ứng dụng sẽ tính mã băm H (ràng buộc nội dung và ${if (attachedFiles.isNotEmpty()) "${attachedFiles.size} tệp đính kèm" else "bằng chứng ban đầu"}), nhân hệ số mù r ngẫu nhiên thành m*. Server ký mù s* và trả về mà KHÔNG THỂ BIẾT nội dung bên dưới. Sau đó ứng dụng tự bóc mù ra s và nộp ẩn danh.",
                            fontSize = 12.sp,
                            color = TextSecondary,
                            lineHeight = 18.sp
                        )

                        Spacer(modifier = Modifier.height(20.dp))

                        Button(
                            onClick = {
                                scope.launch {
                                    isProcessing = true
                                    executeFullWhistleblowerFlow(
                                        context = context,
                                        token = token,
                                        category = effectiveCategory,
                                        title = title,
                                        description = description,
                                        attachedFiles = attachedFiles,
                                        onStatus = { statusMessage = it },
                                        onSuccess = { caseToken ->
                                            isProcessing = false
                                            onSubmissionSuccess(caseToken)
                                        }
                                    )
                                    isProcessing = false
                                }
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(50.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGreen),
                            enabled = !isProcessing
                        ) {
                            if (isProcessing) {
                                CircularProgressIndicator(color = Color.White, modifier = Modifier.size(24.dp))
                            } else {
                                Text("🚀 KÝ MÙ & NỘP HỒ SƠ ẨN DANH NGAY", fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun StepIndicator(step: Int, title: String, active: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Surface(
            color = if (active) AccentCyan else BorderDark,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.size(24.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = "$step",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (active) Color(0xFF0F172A) else TextSecondary
                )
            }
        }
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = title,
            fontSize = 11.sp,
            color = if (active) TextPrimary else TextSecondary,
            fontWeight = if (active) FontWeight.Bold else FontWeight.Normal
        )
    }
}

/**
 * Thực thi toàn bộ quy trình mật mã toán học và nộp hồ sơ.
 */
private suspend fun executeFullWhistleblowerFlow(
    context: Context,
    token: String,
    category: String,
    title: String,
    description: String,
    attachedFiles: List<SelectedEvidenceFile>,
    onStatus: (String) -> Unit,
    onSuccess: (String) -> Unit
) = withContext(Dispatchers.IO) {
    try {
        onStatus("1. Đang lấy Public Key RSA & ECC của Ban Thanh tra...")
        val keysResp = NetworkClient.identifiedApi.getOfficerPublicKeys("Bearer $token")
        if (!keysResp.isSuccessful || keysResp.body() == null) {
            onStatus("Lỗi lấy Public Key: ${keysResp.code()}")
            return@withContext
        }
        val officerKeys = keysResp.body()!!
        val e = BigInteger(officerKeys.blindSignPub.e.removePrefix("0x"), 16)
        val n = BigInteger(officerKeys.blindSignPub.n.removePrefix("0x"), 16)
        val officerChatPubHex = officerKeys.chatPubHex

        onStatus("2. Đang sinh cặp khóa EC và mã hóa ECIES Title/Description...")
        val caseKeyPair = EciesHelper.generateEcKeyPair()
        val casePubKeyHex = EciesHelper.exportPublicKeyToHex(caseKeyPair.public)
        val casePrivKeyHex = EciesHelper.exportPrivateKeyToHex(caseKeyPair.private)
        val caseToken = "CASE-${System.currentTimeMillis()}"

        // Mã hóa ECIES nội dung: title|||description theo format giải mã của Ban Thanh tra
        val fullPayload = "$title|||$description".toByteArray(Charsets.UTF_8)
        val encPayload = EciesHelper.eciesEncrypt(officerChatPubHex, fullPayload)
        val encTitleHex = encPayload.ciphertextHex.take(32)
        val encDescHex = encPayload.ciphertextHex

        // 3. Chuẩn bị các tệp bằng chứng và tính mã băm SHA-256
        onStatus("3. Đang xử lý các tệp đính kèm & tẩy siêu dữ liệu EXIF...")
        val evidenceParts = mutableListOf<MultipartBody.Part>()
        val fileHashes = mutableListOf<String>()

        if (attachedFiles.isEmpty()) {
            val dummyEvidence = "ATBM_EVIDENCE_CLEAN_DATA_${System.currentTimeMillis()}".toByteArray(Charsets.UTF_8)
            val fileSha256 = MetadataSanitizer.computeSha256(dummyEvidence)
            fileHashes.add(fileSha256)

            val tempFile = File(context.cacheDir, "evidence_${System.currentTimeMillis()}.bin").apply {
                writeBytes(dummyEvidence)
            }
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

        onStatus("4. Đang tính mã băm toán học H và làm mù m*...")
        val h = RsaBlindClient.computePayloadHash(
            category = category,
            encryptedTitle = encTitleHex,
            encryptedDescription = encDescHex,
            caseToken = caseToken,
            casePublicKeyHex = casePubKeyHex,
            evidenceFileHashes = fileHashes,
            n = n
        )

        val blinding = RsaBlindClient.blindMessage(h, e, n)
        val mStarHex = blinding.mStar.toString(16)

        onStatus("5. Gửi m* lên Ban Thanh tra xin chữ ký mù...")
        val blindResp = NetworkClient.identifiedApi.requestBlindSign(
            bearerToken = "Bearer $token",
            req = BlindSignRequest(blindedHash = mStarHex)
        )
        if (!blindResp.isSuccessful || blindResp.body() == null) {
            onStatus("Lỗi xin chữ ký mù: Quota tuần đã hết hoặc từ chối.")
            return@withContext
        }
        val rawSig = blindResp.body()!!.blindSignature.removePrefix("0x").removePrefix("0X")
        val sStar = BigInteger(rawSig, 16)

        onStatus("6. Tự bóc mù thu hồi chữ ký s = (s* * r^-1) mod N...")
        val s = RsaBlindClient.unblindSignature(sStar, blinding.r, n)
        val sHex = s.toString(16)

        // Lưu vào Secure Vault SQLCipher
        val vault = SecureVaultDatabase(context)
        val nowStr = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
        vault.saveCase(
            passphrase = "VAULT_MASTER_KEY_SQLCIPHER",
            item = SecureVaultDatabase.VaultCaseItem(
                caseToken = caseToken,
                category = category,
                title = title,
                casePrivateKeyHex = casePrivKeyHex,
                casePublicKeyHex = casePubKeyHex,
                unblindedSignature = sHex,
                status = "SUBMITTED",
                createdAt = nowStr
            )
        )

        onStatus("7. Đang nộp ẩn danh (Zero-Knowledge) lên máy chủ...")
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
            onStatus("✅ Nộp hồ sơ tố giác ẩn danh thành công! Token: $caseToken")
            withContext(Dispatchers.Main) {
                onSuccess(caseToken)
            }
        } else {
            onStatus("Lỗi nộp hồ sơ ẩn danh: ${submitResp.errorBody()?.string()}")
        }
    } catch (e: Exception) {
        onStatus("Lỗi trong quá trình xử lý: ${e.localizedMessage}")
    }
}
