package com.atbm.app.ui.screens

import android.content.Context
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
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }

    var statusMessage by remember { mutableStateOf<String?>(null) }
    var isProcessing by remember { mutableStateOf(false) }

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
                        listOf("Tham nhũng tài chính", "Quấy rối công sở", "Vi phạm bảo mật ATBM", "Gian lận đấu thầu").forEach { cat ->
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
                                   "2. File bằng chứng giả lập sẽ được tẩy sạch 100% EXIF/GPS coordinates.\n" +
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
                            text = "Ứng dụng sẽ tính mã băm H, nhân hệ số mù r ngẫu nhiên thành m*. Server ký mù s* và trả về mà KHÔNG THỂ BIẾT nội dung bên dưới. Sau đó ứng dụng tự bóc mù ra s và nộp ẩn danh.",
                            fontSize = 12.sp,
                            color = TextSecondary,
                            lineHeight = 18.sp
                        )

                        Spacer(modifier = Modifier.height(20.dp))

                        Button(
                            onClick = {
                                scope.launch {
                                    executeFullWhistleblowerFlow(
                                        context = context,
                                        token = token,
                                        category = category,
                                        title = title,
                                        description = description,
                                        onStatus = { statusMessage = it },
                                        onSuccess = { caseToken ->
                                            onSubmissionSuccess(caseToken)
                                        }
                                    )
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

        // Mã hóa ECIES nội dung
        val encTitlePayload = EciesHelper.eciesEncrypt(officerChatPubHex, title.toByteArray(Charsets.UTF_8))
        val encDescPayload = EciesHelper.eciesEncrypt(officerChatPubHex, description.toByteArray(Charsets.UTF_8))

        // Chuẩn bị file bằng chứng giả lập
        val dummyEvidence = "ATBM_EVIDENCE_CLEAN_DATA_${System.currentTimeMillis()}".toByteArray(Charsets.UTF_8)
        val fileSha256 = MetadataSanitizer.computeSha256(dummyEvidence)

        onStatus("3. Đang tính mã băm toán học H và làm mù m*...")
        val h = RsaBlindClient.computePayloadHash(
            category = category,
            encryptedTitle = encTitlePayload.ciphertextHex,
            encryptedDescription = encDescPayload.ciphertextHex,
            caseToken = caseToken,
            casePublicKeyHex = casePubKeyHex,
            evidenceFileHashes = listOf(fileSha256),
            n = n
        )

        val blinding = RsaBlindClient.blindMessage(h, e, n)
        val mStarHex = blinding.mStar.toString(16)

        onStatus("4. Gửi m* lên Ban Thanh tra xin chữ ký mù...")
        val blindResp = NetworkClient.identifiedApi.requestBlindSign(
            bearerToken = "Bearer $token",
            req = BlindSignRequest(blindedHash = mStarHex)
        )
        if (!blindResp.isSuccessful || blindResp.body() == null) {
            onStatus("Lỗi xin chữ ký mù: Quota tuần đã hết hoặc từ chối.")
            return@withContext
        }
        val sStar = BigInteger(blindResp.body()!!.blindSignature, 16)

        onStatus("5. Tự bóc mù thu hồi chữ ký s = (s* * r^-1) mod N...")
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

        onStatus("6. Đang nộp ẩn danh (Zero-Knowledge) lên máy chủ...")
        val textType = "text/plain".toMediaTypeOrNull()
        val binType = "application/octet-stream".toMediaTypeOrNull()

        val tempFile = File(context.cacheDir, "evidence.bin").apply {
            writeBytes(dummyEvidence)
        }
        val filePart = MultipartBody.Part.createFormData(
            "files",
            "evidence.bin",
            tempFile.asRequestBody(binType)
        )

        val submitResp = NetworkClient.anonymousApi.submitCase(
            category = category.toRequestBody(textType),
            encryptedTitle = encTitlePayload.ciphertextHex.toRequestBody(textType),
            encryptedDescription = encDescPayload.ciphertextHex.toRequestBody(textType),
            payloadEphemeralPub = encTitlePayload.ephemeralPublicKeyHex.toRequestBody(textType),
            payloadIv = encTitlePayload.ivHex.toRequestBody(textType),
            payloadAuthTag = encTitlePayload.authTagHex.toRequestBody(textType),
            caseToken = caseToken.toRequestBody(textType),
            casePublicKey = casePubKeyHex.toRequestBody(textType),
            unblindedSignature = sHex.toRequestBody(textType),
            files = listOf(filePart)
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
