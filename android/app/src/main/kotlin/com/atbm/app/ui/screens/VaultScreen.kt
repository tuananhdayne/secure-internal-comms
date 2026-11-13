package com.atbm.app.ui.screens

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.atbm.app.data.api.CaseDetailResponse
import com.atbm.app.data.api.NetworkClient
import com.atbm.app.data.api.SendMessageRequest
import com.atbm.app.data.db.SecureVaultDatabase
import com.atbm.app.domain.crypto.EciesHelper
import com.atbm.app.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VaultScreen(
    onNavigateBack: () -> Unit,
    onPanicWiped: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var casesList by remember { mutableStateOf<List<SecureVaultDatabase.VaultCaseItem>>(emptyList()) }
    var selectedCase by remember { mutableStateOf<SecureVaultDatabase.VaultCaseItem?>(null) }
    var serverCaseDetail by remember { mutableStateOf<CaseDetailResponse?>(null) }
    var chatInput by remember { mutableStateOf("") }
    var showPanicDialog by remember { mutableStateOf(false) }
    var panicPinInput by remember { mutableStateOf("") }

    val loadVaultCases = {
        scope.launch(Dispatchers.IO) {
            val vault = SecureVaultDatabase(context)
            val list = vault.getAllCases("VAULT_MASTER_KEY_SQLCIPHER")
            withContext(Dispatchers.Main) {
                casesList = list
            }
        }
    }

    LaunchedEffect(Unit) {
        loadVaultCases()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Secure Vault (Hồ Sơ Của Bạn)",
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
                actions = {
                    // Nút làm mới / đồng bộ thông báo
                    IconButton(onClick = {
                        scope.launch {
                            com.atbm.app.domain.notification.CaseNotificationManager.checkCaseUpdates(context)
                            loadVaultCases()
                        }
                    }) {
                        Text("🔄", fontSize = 18.sp)
                    }
                    // Nút Kích hoạt Panic PIN Khẩn cấp
                    IconButton(onClick = { showPanicDialog = true }) {
                        Text("🚨", fontSize = 20.sp)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = CardDark)
            )
        },
        containerColor = BgDark
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            if (casesList.isEmpty()) {
                Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text("🗄️", fontSize = 48.sp)
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = "Chưa có hồ sơ nào trong Secure Vault.",
                        fontSize = 14.sp,
                        color = TextSecondary
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(casesList) { c ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    selectedCase = c
                                    scope.launch(Dispatchers.IO) {
                                        try {
                                            val resp = NetworkClient.anonymousApi.getCaseStatus(c.caseToken)
                                            if (resp.isSuccessful && resp.body() != null) {
                                                val detail = resp.body()!!
                                                withContext(Dispatchers.Main) {
                                                    serverCaseDetail = detail
                                                }
                                                // Xóa cờ chưa đọc trong SQLCipher local khi người dùng đã mở xem
                                                val vault = SecureVaultDatabase(context)
                                                vault.markCaseAsRead("VAULT_MASTER_KEY_SQLCIPHER", c.caseToken, detail.messages.size)
                                                val updatedList = vault.getAllCases("VAULT_MASTER_KEY_SQLCIPHER")
                                                withContext(Dispatchers.Main) {
                                                    casesList = updatedList
                                                }
                                            }
                                        } catch (_: Exception) {}
                                    }
                                },
                            colors = CardDefaults.cardColors(containerColor = CardDark),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = c.caseToken,
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = AccentCyan
                                    )
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                                    ) {
                                        if (c.hasUnread) {
                                            Surface(
                                                color = Color(0xFFEF4444).copy(alpha = 0.2f),
                                                shape = RoundedCornerShape(4.dp),
                                                border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFEF4444))
                                            ) {
                                                Text(
                                                    text = "🔔 CÓ PHẢN HỒI MỚI",
                                                    color = Color(0xFFEF4444),
                                                    fontSize = 9.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                                )
                                            }
                                        }
                                        Surface(
                                            color = AccentGreen.copy(alpha = 0.2f),
                                            shape = RoundedCornerShape(4.dp)
                                        ) {
                                            Text(
                                                text = c.status,
                                                color = AccentGreen,
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.Bold,
                                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                            )
                                        }
                                    }
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    text = c.title,
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = TextPrimary
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "Chuyên mục: ${c.category} • Ngày tạo: ${c.createdAt}",
                                    fontSize = 11.sp,
                                    color = TextSecondary
                                )
                            }
                        }
                    }
                }
            }

            // Chat & Chi tiết Modal
            if (selectedCase != null) {
                val curCase = selectedCase!!
                AlertDialog(
                    onDismissRequest = {
                        selectedCase = null
                        serverCaseDetail = null
                    },
                    confirmButton = {
                        Button(onClick = {
                            selectedCase = null
                            serverCaseDetail = null
                        }) {
                            Text("Đóng")
                        }
                    },
                    title = {
                        Text(
                            text = "Tra Cứu & Chat E2EE (${curCase.caseToken})",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                    },
                    text = {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 400.dp)
                        ) {
                            Text(
                                text = "Tiêu đề: ${curCase.title}",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            Text(
                                text = "Trạng thái máy chủ: ${serverCaseDetail?.status ?: "Đang đồng bộ..."}",
                                fontSize = 12.sp,
                                color = AccentAmber
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            HorizontalDivider(color = BorderDark)
                            Spacer(modifier = Modifier.height(8.dp))

                            Text("Lịch sử tin nhắn bảo mật (E2EE):", fontSize = 12.sp, color = TextSecondary)
                            Spacer(modifier = Modifier.height(6.dp))

                            val messages = serverCaseDetail?.messages ?: emptyList()
                            if (messages.isEmpty()) {
                                Text("Chưa có tin nhắn phản hồi nào từ Ban Thanh tra.", fontSize = 11.sp, color = TextSecondary)
                            } else {
                                LazyColumn(modifier = Modifier.weight(1f)) {
                                    items(messages) { msg ->
                                        val isFromMe = (msg.senderRole == "ANONYMOUS_WHISTLEBLOWER" || msg.senderRole == "WHISTLEBLOWER")
                                        val senderText = if (isFromMe) "Tôi (Người tố cáo)" else "Ban Thanh tra (Officer)"
                                        
                                        var decryptedText = if (isFromMe) "[Tin nhắn đã gửi đi - E2EE]" else "[Nội dung mã hóa]"
                                        if (!isFromMe) {
                                            try {
                                                val privKey = EciesHelper.importPrivateKeyFromHex(curCase.casePrivateKeyHex)
                                                val raw = EciesHelper.eciesDecrypt(
                                                    recipientPrivateKey = privKey,
                                                    ephemeralPublicKeyHex = msg.ephemeralPublicKey,
                                                    ivHex = msg.iv,
                                                    ciphertextHex = msg.ciphertext,
                                                    authTagHex = msg.authTag
                                                )
                                                decryptedText = String(raw, Charsets.UTF_8)
                                            } catch (_: Exception) {
                                                decryptedText = "[Giải mã thất bại]"
                                            }
                                        }

                                        Surface(
                                            color = if (isFromMe) CardDark else Color(0xFF1E3A8A),
                                            shape = RoundedCornerShape(8.dp),
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(vertical = 4.dp)
                                        ) {
                                            Column(modifier = Modifier.padding(8.dp)) {
                                                Text(senderText, fontSize = 10.sp, color = AccentCyan, fontWeight = FontWeight.Bold)
                                                Text(decryptedText, fontSize = 12.sp, color = TextPrimary)
                                            }
                                        }
                                    }
                                }
                            }

                            Spacer(modifier = Modifier.height(8.dp))

                            Row(verticalAlignment = Alignment.CenterVertically) {
                                OutlinedTextField(
                                    value = chatInput,
                                    onValueChange = { chatInput = it },
                                    placeholder = { Text("Nhập tin nhắn bổ sung...") },
                                    modifier = Modifier.weight(1f),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedTextColor = TextPrimary,
                                        unfocusedTextColor = TextPrimary
                                    )
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Button(
                                    onClick = {
                                        if (chatInput.isNotBlank()) {
                                            val textToSend = chatInput
                                            scope.launch(Dispatchers.IO) {
                                                try {
                                                    val privKey = EciesHelper.importPrivateKeyFromHex(curCase.casePrivateKeyHex)
                                                    val officerPubHex = NetworkClient.identifiedApi.getOfficerPublicKeys("").body()?.chatPubHex
                                                        ?: return@launch
                                                    val encMsg = EciesHelper.eciesEncrypt(
                                                        officerPubHex,
                                                        textToSend.toByteArray(Charsets.UTF_8)
                                                    )
                                                    // Ký số ECDSA trên nội dung encrypted_message
                                                    val sig = EciesHelper.signMessage(privKey, encMsg.ciphertextHex.toByteArray(Charsets.UTF_8))

                                                    val resp = NetworkClient.anonymousApi.sendMessage(
                                                        caseToken = curCase.caseToken,
                                                        req = SendMessageRequest(
                                                            ephemeralPublicKey = encMsg.ephemeralPublicKeyHex,
                                                            iv = encMsg.ivHex,
                                                            ciphertext = encMsg.ciphertextHex,
                                                            authTag = encMsg.authTagHex,
                                                            senderSignature = sig
                                                        )
                                                    )
                                                    if (resp.isSuccessful) {
                                                        val updated = NetworkClient.anonymousApi.getCaseStatus(curCase.caseToken)
                                                        withContext(Dispatchers.Main) {
                                                            if (updated.isSuccessful) {
                                                                serverCaseDetail = updated.body()
                                                            }
                                                            chatInput = ""
                                                        }
                                                    }
                                                } catch (_: Exception) {}
                                            }
                                        }
                                    }
                                ) {
                                    Text("Gửi")
                                }
                            }
                        }
                    },
                    containerColor = CardDark
                )
            }

            // PANIC PIN DIALOG
            if (showPanicDialog) {
                AlertDialog(
                    onDismissRequest = { showPanicDialog = false },
                    confirmButton = {
                        Button(
                            onClick = {
                                if (panicPinInput == "999999") {
                                    // KÍCH HOẠT TIÊU HỦY DỮ LIỆU KHẨN CẤP
                                    val vault = SecureVaultDatabase(context)
                                    vault.emergencyWipe()
                                    showPanicDialog = false
                                    onPanicWiped()
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentRed)
                        ) {
                            Text("XÁC NHẬN TIÊU HỦY")
                        }
                    },
                    dismissButton = {
                        OutlinedButton(onClick = { showPanicDialog = false }) {
                            Text("Hủy")
                        }
                    },
                    title = {
                        Text("🚨 CẢNH BÁO: CHẾ ĐỘ PANIC PIN", color = AccentRed, fontWeight = FontWeight.Bold)
                    },
                    text = {
                        Column {
                            Text(
                                "Nếu bạn đang bị cưỡng ép kiểm tra thiết bị, nhập mã PANIC PIN (999999) để tiến hành Overwrite Shredding tiêu hủy toàn bộ kho bí mật trong tích tắc.",
                                fontSize = 12.sp,
                                color = TextSecondary
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            OutlinedTextField(
                                value = panicPinInput,
                                onValueChange = { panicPinInput = it },
                                placeholder = { Text("Nhập 999999...") },
                                modifier = Modifier.fillMaxWidth(),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = TextPrimary,
                                    unfocusedTextColor = TextPrimary
                                )
                            )
                        }
                    },
                    containerColor = CardDark
                )
            }
        }
    }
}
