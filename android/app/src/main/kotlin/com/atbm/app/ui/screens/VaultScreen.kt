package com.atbm.app.ui.screens

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.DeleteForever
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.Password
import androidx.compose.material.icons.outlined.Refresh
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
import com.atbm.app.ui.components.DisplayText
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
    var showCodeDialog by remember { mutableStateOf(false) }
    var codeCurrent by remember { mutableStateOf("") }
    var codeNew by remember { mutableStateOf("") }
    var codeConfirm by remember { mutableStateOf("") }
    var codeError by remember { mutableStateOf<String?>(null) }
    var panicPinInput by remember { mutableStateOf("") }
    var panicPinError by remember { mutableStateOf(false) }
    var chatError by remember { mutableStateOf<String?>(null) }
    var isSending by remember { mutableStateOf(false) }

    val loadVaultCases = {
        scope.launch(Dispatchers.IO) {
            val vault = SecureVaultDatabase(context)
            val list = vault.getAllCases()
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
                        text = "Tố giác của tôi",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Quay lại", tint = TextPrimary)
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
                        Icon(Icons.Outlined.Refresh, contentDescription = "Làm mới", tint = TextPrimary)
                    }
                    // Nút Kích hoạt Panic PIN Khẩn cấp
                    IconButton(onClick = { showCodeDialog = true; codeError = null }) {
                        Icon(Icons.Outlined.Password, contentDescription = "Đặt mã khẩn cấp", tint = TextPrimary)
                    }
                    IconButton(onClick = { showPanicDialog = true }) {
                        Icon(Icons.Outlined.DeleteForever, contentDescription = "Xóa nhanh dữ liệu", tint = AccentRed)
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
                    Icon(Icons.Outlined.Inventory2, contentDescription = null, tint = TextSecondary, modifier = Modifier.size(48.dp))
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Bạn chưa gửi tố giác nào", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                    Text(
                        text = "Các tố giác bạn gửi từ máy này sẽ hiển thị tại đây để theo dõi tiến độ.",
                        fontSize = 12.sp,
                        color = TextSecondary,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 24.dp, vertical = 4.dp)
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
                                    chatError = null
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
                                                vault.markCaseAsRead(c.caseToken, detail.messages.size)
                                                val updatedList = vault.getAllCases()
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
                                        text = "Mã " + DisplayText.shortCaseCode(c.caseToken),
                                        fontSize = 12.sp,
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
                                                    text = "Có cập nhật mới",
                                                    color = Color(0xFFEF4444),
                                                    fontSize = 9.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                                )
                                            }
                                        }
                                        val st = DisplayText.caseStatus(c.status)
                                        Surface(
                                            color = st.color.copy(alpha = 0.2f),
                                            shape = RoundedCornerShape(4.dp)
                                        ) {
                                            Text(
                                                text = st.text,
                                                color = st.color,
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
                                    text = "${c.category} • Gửi lúc ${DisplayText.localDateTime(c.createdAt)}",
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
                            text = "Tố giác " + DisplayText.shortCaseCode(curCase.caseToken),
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
                                text = curCase.title,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            Text(
                                text = "Trạng thái: " + (serverCaseDetail?.let { DisplayText.caseStatus(it.status).text } ?: "đang tải…"),
                                fontSize = 12.sp,
                                color = serverCaseDetail?.let { DisplayText.caseStatus(it.status).color } ?: TextSecondary
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            HorizontalDivider(color = BorderDark)
                            Spacer(modifier = Modifier.height(8.dp))

                            Text("Trao đổi với Ban Thanh tra", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = TextSecondary)
                            Spacer(modifier = Modifier.height(6.dp))

                            val messages = serverCaseDetail?.messages ?: emptyList()
                            if (messages.isEmpty()) {
                                Text("Chưa có tin nhắn. Ban Thanh tra sẽ liên hệ tại đây nếu cần thêm thông tin; bạn cũng có thể gửi bổ sung bất cứ lúc nào.", fontSize = 11.sp, color = TextSecondary)
                            } else {
                                LazyColumn(modifier = Modifier.weight(1f)) {
                                    items(messages) { msg ->
                                        val isFromMe = (msg.senderRole == "ANONYMOUS_WHISTLEBLOWER" || msg.senderRole == "WHISTLEBLOWER")
                                        val senderText = if (isFromMe) "Bạn" else "Ban Thanh tra"
                                        
                                        var decryptedText = if (isFromMe) "(Tin nhắn bạn đã gửi — chỉ Ban Thanh tra đọc được)" else ""
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
                                                decryptedText = "(Không thể hiển thị tin nhắn này)"
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
                                    placeholder = { Text("Nhập thông tin bổ sung…") },
                                    modifier = Modifier.weight(1f),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedTextColor = TextPrimary,
                                        unfocusedTextColor = TextPrimary
                                    )
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Button(
                                    enabled = !isSending,
                                    onClick = {
                                        if (chatInput.isNotBlank()) {
                                            val textToSend = chatInput
                                            isSending = true
                                            chatError = null
                                            scope.launch(Dispatchers.IO) {
                                                try {
                                                    val privKey = EciesHelper.importPrivateKeyFromHex(curCase.casePrivateKeyHex)
                                                    val officerPubHex = NetworkClient.identifiedApi.getOfficerPublicKeys("").body()?.chatPubHex
                                                    if (officerPubHex == null) {
                                                        withContext(Dispatchers.Main) {
                                                            chatError = "Không thể kết nối tới hệ thống. Vui lòng thử lại."
                                                            isSending = false
                                                        }
                                                        return@launch
                                                    }
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
                                                    } else {
                                                        withContext(Dispatchers.Main) { chatError = "Gửi tin nhắn không thành công. Vui lòng thử lại." }
                                                    }
                                                } catch (e: Exception) {
                                                    withContext(Dispatchers.Main) { chatError = DisplayText.networkError(e) }
                                                } finally {
                                                    withContext(Dispatchers.Main) { isSending = false }
                                                }
                                            }
                                        }
                                    }
                                ) {
                                    Text("Gửi")
                                }
                            }
                            if (chatError != null) {
                                Text(chatError ?: "", fontSize = 11.sp, color = AccentRed, modifier = Modifier.padding(top = 4.dp))
                            }
                        }
                    },
                    containerColor = CardDark
                )
            }

            // ĐẶT / ĐỔI MÃ KHẨN CẤP
            if (showCodeDialog) {
                val isCustom = com.atbm.app.data.security.EmergencyCode.isCustom(context)
                val close = {
                    showCodeDialog = false; codeCurrent = ""; codeNew = ""; codeConfirm = ""; codeError = null
                }
                val pinField: @Composable (String, String, (String) -> Unit) -> Unit = { label, value, onChange ->
                    OutlinedTextField(
                        value = value,
                        onValueChange = { onChange(it.filter(Char::isDigit).take(8)); codeError = null },
                        label = { Text(label) },
                        singleLine = true,
                        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.NumberPassword),
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                        colors = OutlinedTextFieldDefaults.colors(focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
                    )
                }
                AlertDialog(
                    onDismissRequest = close,
                    title = { Text("Mã khẩn cấp", fontWeight = FontWeight.Bold) },
                    text = {
                        Column {
                            Text(
                                if (isCustom) "Đổi mã dùng để xóa nhanh dữ liệu trên máy."
                                else "Bạn đang dùng mã mặc định. Hãy đặt mã riêng (6–8 chữ số) mà chỉ bạn biết.",
                                fontSize = 12.sp, color = TextSecondary
                            )
                            pinField(if (isCustom) "Mã hiện tại" else "Mã hiện tại (mặc định trong hướng dẫn)", codeCurrent) { codeCurrent = it }
                            pinField("Mã mới", codeNew) { codeNew = it }
                            pinField("Nhập lại mã mới", codeConfirm) { codeConfirm = it }
                            if (codeError != null) {
                                Text(codeError ?: "", color = AccentRed, fontSize = 12.sp, modifier = Modifier.padding(top = 6.dp))
                            }
                        }
                    },
                    confirmButton = {
                        Button(
                            onClick = {
                                codeError = when {
                                    !com.atbm.app.data.security.EmergencyCode.isValidFormat(codeNew) -> "Mã mới phải gồm 6–8 chữ số."
                                    codeNew != codeConfirm -> "Hai lần nhập mã mới không khớp."
                                    !com.atbm.app.data.security.EmergencyCode.change(context, codeCurrent, codeNew) -> "Mã hiện tại không đúng."
                                    else -> null
                                }
                                if (codeError == null) {
                                    close()
                                    android.widget.Toast.makeText(context, "Đã lưu mã khẩn cấp mới.", android.widget.Toast.LENGTH_SHORT).show()
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentBlue, contentColor = Color.White)
                        ) { Text("Lưu") }
                    },
                    dismissButton = { OutlinedButton(onClick = close) { Text("Hủy") } },
                    containerColor = CardDark
                )
            }

            // PANIC PIN DIALOG
            if (showPanicDialog) {
                AlertDialog(
                    onDismissRequest = { showPanicDialog = false; panicPinInput = ""; panicPinError = false },
                    confirmButton = {
                        Button(
                            onClick = {
                                panicPinError = false
                                if (com.atbm.app.data.security.EmergencyCode.matches(context, panicPinInput)) {
                                    // KÍCH HOẠT TIÊU HỦY DỮ LIỆU KHẨN CẤP
                                    val vault = SecureVaultDatabase(context)
                                    vault.emergencyWipe()
                                    showPanicDialog = false
                                    panicPinInput = ""
                                    onPanicWiped()
                                } else {
                                    panicPinError = true
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentRed, contentColor = Color.White)
                        ) {
                            Text("Xóa dữ liệu")
                        }
                    },
                    dismissButton = {
                        OutlinedButton(onClick = { showPanicDialog = false; panicPinInput = ""; panicPinError = false }) {
                            Text("Hủy")
                        }
                    },
                    title = {
                        Text("Xóa nhanh dữ liệu trên máy", color = AccentRed, fontWeight = FontWeight.Bold)
                    },
                    text = {
                        Column {
                            Text(
                                "Dùng khi bạn cần xóa ngay mọi dấu vết tố giác trên điện thoại này. Toàn bộ tố giác đã lưu sẽ bị xóa vĩnh viễn và không thể khôi phục.\n\nNhập mã khẩn cấp để xác nhận.",
                                fontSize = 12.sp,
                                color = TextSecondary
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            OutlinedTextField(
                                value = panicPinInput,
                                onValueChange = { panicPinInput = it.filter(Char::isDigit).take(12); panicPinError = false },
                                placeholder = { Text("Mã khẩn cấp") },
                                singleLine = true,
                                isError = panicPinError,
                                supportingText = if (panicPinError) { { Text("Mã không đúng.") } } else null,
                                visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.NumberPassword),
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
