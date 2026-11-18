package com.atbm.app.ui.screens

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.LocationOff
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
import com.atbm.app.ui.components.DisplayText
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
                    mime.startsWith("image/") -> "Ảnh"
                    mime.startsWith("video/") -> "Video"
                    mime.startsWith("audio/") -> "Ghi âm"
                    mime.contains("pdf") -> "PDF"
                    else -> "Tài liệu"
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
                        text = "Gửi tố giác ẩn danh",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                },
                navigationIcon = {
                    IconButton(onClick = {
                        if (currentStep > 1 && !isProcessing) { currentStep -= 1; statusMessage = null } else onNavigateBack()
                    }) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Quay lại", tint = TextPrimary)
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
                StepIndicator(step = 2, title = "Xem lại", active = currentStep >= 2)
                StepIndicator(step = 3, title = "Gửi đi", active = currentStep >= 3)
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
                        Text("Bạn muốn tố giác về vấn đề gì?", fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                        Spacer(modifier = Modifier.height(6.dp))
                        listOf("Tham nhũng tài chính", "Quấy rối công sở", "Vi phạm an toàn thông tin", "Gian lận đấu thầu", "Khác").forEach { cat ->
                            // Cả dòng (chữ + nút) đều chọn được, đúng vai trò "radio" cho trình đọc màn hình
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .selectable(
                                        selected = (category == cat),
                                        onClick = { category = cat },
                                        role = androidx.compose.ui.semantics.Role.RadioButton
                                    )
                                    .heightIn(min = 48.dp)
                                    .padding(horizontal = 4.dp)
                            ) {
                                RadioButton(
                                    selected = (category == cat),
                                    onClick = null,
                                    colors = RadioButtonDefaults.colors(selectedColor = AccentCyan)
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Text(cat, fontSize = 14.sp, color = TextPrimary)
                            }
                        }

                        if (category == "Khác") {
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = customCategory,
                                onValueChange = { customCategory = it },
                                label = { Text("Vấn đề khác (không bắt buộc)") },
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
                            label = { Text("Tiêu đề ngắn gọn") },
                            placeholder = { Text("VD: Chi khống tiền công tác phí quý 3") },
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
                            label = { Text("Mô tả chi tiết") },
                            placeholder = { Text("Sự việc gì, xảy ra khi nào, ở đâu, ai liên quan…") },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 4,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            )
                        )

                        Spacer(modifier = Modifier.height(14.dp))
                        Text(
                            "Đính kèm bằng chứng (không bắt buộc)",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "Ảnh, video, ghi âm hoặc tài liệu. Thông tin vị trí và thiết bị trong ảnh sẽ được tự động xóa trước khi gửi.",
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
                                Icon(Icons.Outlined.Image, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Ảnh/Video", fontSize = 11.sp)
                            }
                            OutlinedButton(
                                onClick = { filePickerLauncher.launch("audio/*") },
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentGreen)
                            ) {
                                Icon(Icons.Outlined.Mic, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Ghi âm", fontSize = 11.sp)
                            }
                            OutlinedButton(
                                onClick = { filePickerLauncher.launch("*/*") },
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 4.dp, vertical = 6.dp),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentAmber)
                            ) {
                                Icon(Icons.Outlined.Description, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Tài liệu", fontSize = 11.sp)
                            }
                        }

                        if (attachedFiles.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(10.dp))
                            Text(
                                "Đã chọn ${attachedFiles.size} tệp",
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
                                                Icon(
                                                    when (fileItem.typeLabel) {
                                                        "Ảnh", "Video" -> Icons.Outlined.Image
                                                        "Ghi âm" -> Icons.Outlined.Mic
                                                        else -> Icons.Outlined.Description
                                                    },
                                                    contentDescription = fileItem.typeLabel,
                                                    tint = AccentCyan,
                                                    modifier = Modifier.padding(end = 8.dp).size(18.dp)
                                                )
                                                Column {
                                                    Text(
                                                        text = fileItem.name,
                                                        fontSize = 12.sp,
                                                        color = TextPrimary,
                                                        maxLines = 1,
                                                        overflow = TextOverflow.Ellipsis
                                                    )
                                                    Text(
                                                        text = "${fileItem.typeLabel} • ${formatFileSize(fileItem.size)}",
                                                        fontSize = 10.sp,
                                                        color = TextSecondary
                                                    )
                                                }
                                            }
                                            IconButton(
                                                onClick = { attachedFiles = attachedFiles.filter { it.uri != fileItem.uri } },
                                                modifier = Modifier.size(28.dp)
                                            ) {
                                                Icon(Icons.Outlined.Close, contentDescription = "Bỏ tệp này", tint = Color(0xFFEF4444), modifier = Modifier.size(16.dp))
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
                                    statusMessage = null
                                    currentStep = 2
                                } else {
                                    statusMessage = "Vui lòng nhập tiêu đề và mô tả chi tiết trước khi tiếp tục."
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = AccentBlue, contentColor = Color.White)
                        ) {
                            Text("Tiếp tục", fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }

            // GIAO DIỆN BƯỚC 2: XEM LẠI
            if (currentStep == 2) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Kiểm tra lại nội dung", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                        Spacer(modifier = Modifier.height(12.dp))
                        ReviewRow("Vấn đề", effectiveCategory)
                        ReviewRow("Tiêu đề", title)
                        ReviewRow("Mô tả", description, maxLines = 4)
                        ReviewRow("Tệp đính kèm", if (attachedFiles.isEmpty()) "Không có" else "${attachedFiles.size} tệp")

                        Spacer(modifier = Modifier.height(12.dp))
                        HorizontalDivider(color = BorderDark)
                        Spacer(modifier = Modifier.height(12.dp))

                        Text("Thông tin của bạn được bảo vệ thế nào?", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                        Spacer(modifier = Modifier.height(8.dp))
                        PrivacyPoint(Icons.Outlined.VisibilityOff, "Không ai biết bạn là người gửi — kể cả Ban Thanh tra và Quản trị viên.")
                        PrivacyPoint(Icons.Outlined.Lock, "Nội dung được khóa ngay trên điện thoại, chỉ Ban Thanh tra mở được.")
                        PrivacyPoint(Icons.Outlined.LocationOff, "Vị trí và thông tin thiết bị trong ảnh được xóa trước khi gửi.")

                        Spacer(modifier = Modifier.height(20.dp))

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(
                                onClick = { currentStep = 1 },
                                modifier = Modifier.weight(1f)
                            ) { Text("Sửa lại") }
                            Button(
                                onClick = { currentStep = 3 },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(containerColor = AccentBlue, contentColor = Color.White)
                            ) {
                                Text("Tiếp tục", fontWeight = FontWeight.SemiBold)
                            }
                        }
                    }
                }
            }

            // GIAO DIỆN BƯỚC 3: GỬI (ký mù + nộp ẩn danh chạy ngầm)
            if (currentStep == 3) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CardDark),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Sẵn sàng gửi", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Ứng dụng sẽ xác nhận bạn là nhân viên hợp lệ rồi gửi tố giác đi dưới dạng ẩn danh. " +
                                "Hệ thống chỉ biết có một nhân viên đã gửi, không biết đó là ai.\n\n" +
                                "Mỗi tuần bạn được gửi tối đa 5 tố giác. Sau khi gửi, bạn có thể theo dõi tiến độ trong mục \"Tố giác của tôi\".",
                            fontSize = 13.sp,
                            color = TextSecondary,
                            lineHeight = 19.sp
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
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = Color.White),
                            enabled = !isProcessing
                        ) {
                            if (isProcessing) {
                                CircularProgressIndicator(color = Color.White, modifier = Modifier.size(24.dp))
                            } else {
                                Text("Gửi tố giác", fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ReviewRow(label: String, value: String, maxLines: Int = 2) {
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Text(label, fontSize = 11.sp, color = TextSecondary)
        Text(value, fontSize = 13.sp, color = TextPrimary, maxLines = maxLines, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun PrivacyPoint(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(verticalAlignment = Alignment.Top, modifier = Modifier.padding(vertical = 4.dp)) {
        Icon(icon, contentDescription = null, tint = AccentGreen, modifier = Modifier.size(18.dp))
        Spacer(modifier = Modifier.width(10.dp))
        Text(text, fontSize = 12.sp, color = TextSecondary, lineHeight = 17.sp)
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

                val s = RsaBlindClient.unblindSignature(sStar, blinding.r, n)
        val sHex = s.toString(16)

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
