package com.atbm.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalContext
import com.atbm.app.data.api.NetworkClient
import com.atbm.app.data.api.ServerAddress
import com.atbm.app.ui.components.DisplayText
import com.atbm.app.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    onLoginSuccess: (token: String, role: String, empCode: String) -> Unit,
    onDirectAnonymousAccess: () -> Unit
) {
    var employeeCode by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }
    val context = LocalContext.current
    // Ô nhập chỉ cần IP (vd. 192.168.1.38) — app tự thêm https:// và cổng 8443
    var serverInput by remember { mutableStateOf(ServerAddress.display(NetworkClient.getBaseUrl())) }
    var checkingServer by remember { mutableStateOf(false) }
    var serverStatus by remember { mutableStateOf<Pair<Boolean, String>?>(null) }  // (ok, thông báo)
    var showConnectionSettings by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var isLoading by remember { mutableStateOf(false) }

    val scope = rememberCoroutineScope()

    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedTextColor = TextPrimary,
        unfocusedTextColor = TextPrimary,
        focusedBorderColor = AccentCyan,
        unfocusedBorderColor = BorderDark,
        focusedLabelColor = AccentCyan,
        focusedLeadingIconColor = AccentCyan,
        unfocusedLeadingIconColor = TextSecondary
    )

    /** Áp dụng + lưu địa chỉ máy chủ đang nhập (bản release: luôn là địa chỉ cố định lúc build). */
    fun applyServerAddress(): Boolean {
        if (!NetworkClient.allowServerEdit) return true
        val url = ServerAddress.normalize(serverInput) ?: return false
        return NetworkClient.saveServerUrl(context, url)
    }

    val checkServer: () -> Unit = check@{
        val url = ServerAddress.normalize(serverInput)
        if (url == null) {
            serverStatus = false to "Địa chỉ không hợp lệ. Ví dụ: 192.168.1.38"
            return@check
        }
        scope.launch {
            checkingServer = true
            serverStatus = try {
                if (NetworkClient.checkServer(url)) {
                    NetworkClient.saveServerUrl(context, url)
                    true to "Đã kết nối máy chủ ✓"
                } else false to "Địa chỉ này không phải máy chủ Cổng Nội Bộ."
            } catch (e: javax.net.ssl.SSLException) {
                false to "Chứng chỉ chưa có IP này. Trên máy chủ chạy lại ./dev.sh lan"
            } catch (e: java.net.SocketTimeoutException) {
                false to "Không kết nối được. Kiểm tra lại IP và mạng Wi-Fi."
            } catch (e: Exception) {
                false to "Không kết nối được. Kiểm tra lại IP và mạng Wi-Fi."
            } finally {
                checkingServer = false
            }
        }
    }

    val doLogin: () -> Unit = login@{
        if (employeeCode.isBlank() || password.isEmpty()) {
            errorMessage = "Vui lòng nhập mã nhân viên và mật khẩu."
            return@login
        }
        if (!applyServerAddress()) {
            showConnectionSettings = true
            errorMessage = "Địa chỉ máy chủ không hợp lệ (ví dụ: 192.168.1.38)."
            return@login
        }
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val response = NetworkClient.identifiedApi.login(
                    employeeCode = employeeCode.trim(),
                    password = password
                )
                val body = response.body()
                if (response.isSuccessful && body != null) {
                    onLoginSuccess(body.accessToken, body.role ?: "EMPLOYEE", employeeCode.trim())
                } else {
                    errorMessage = when (response.code()) {
                        400, 401 -> "Mã nhân viên hoặc mật khẩu không đúng."
                        403 -> "Tài khoản này không thể đăng nhập ứng dụng (đã bị khóa hoặc là tài khoản quản trị chỉ dùng trên web). Vui lòng liên hệ Quản trị viên."
                        429 -> "Bạn đã thử đăng nhập quá nhiều lần. Vui lòng đợi ít phút rồi thử lại."
                        in 500..599 -> "Hệ thống đang bận. Vui lòng thử lại sau."
                        else -> "Đăng nhập không thành công. Vui lòng thử lại."
                    }
                }
            } catch (e: Exception) {
                errorMessage = DisplayText.networkError(e)
            } finally {
                isLoading = false
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BgDark)
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(
                color = AccentCyan.copy(alpha = 0.15f),
                shape = CircleShape,
                modifier = Modifier.size(64.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Shield, contentDescription = null, tint = AccentCyan, modifier = Modifier.size(32.dp))
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Cổng Nội Bộ",
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Text(
                text = "Bảng tin công ty & kênh tố giác an toàn",
                fontSize = 13.sp,
                color = TextSecondary,
                modifier = Modifier.padding(top = 4.dp)
            )

            Spacer(modifier = Modifier.height(24.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CardDark),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text("Đăng nhập", fontSize = 18.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                    Text(
                        "Sử dụng tài khoản do công ty cấp.",
                        fontSize = 12.sp,
                        color = TextSecondary,
                        modifier = Modifier.padding(top = 2.dp, bottom = 16.dp)
                    )

                    if (errorMessage != null) {
                        Surface(
                            color = AccentRed.copy(alpha = 0.15f),
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = errorMessage ?: "",
                                color = Color(0xFFFCA5A5),
                                fontSize = 13.sp,
                                modifier = Modifier.padding(12.dp)
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                    }

                    OutlinedTextField(
                        value = employeeCode,
                        onValueChange = { employeeCode = it; errorMessage = null },
                        label = { Text("Mã nhân viên") },
                        placeholder = { Text("VD: NV001") },
                        leadingIcon = { Icon(Icons.Outlined.Badge, contentDescription = null) },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = fieldColors
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it; errorMessage = null },
                        label = { Text("Mật khẩu") },
                        leadingIcon = { Icon(Icons.Outlined.Lock, contentDescription = null) },
                        trailingIcon = {
                            IconButton(onClick = { showPassword = !showPassword }) {
                                Icon(
                                    if (showPassword) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                                    contentDescription = if (showPassword) "Ẩn mật khẩu" else "Hiện mật khẩu",
                                    tint = TextSecondary
                                )
                            }
                        },
                        singleLine = true,
                        visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = fieldColors
                    )

                    Spacer(modifier = Modifier.height(20.dp))

                    Button(
                        onClick = doLogin,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(50.dp),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = AccentBlue, contentColor = Color.White),
                        enabled = !isLoading
                    ) {
                        if (isLoading) {
                            CircularProgressIndicator(color = Color.White, modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            Text("Đăng nhập", fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                        }
                    }

                    Text(
                        "Quên mật khẩu? Vui lòng liên hệ bộ phận Nhân sự hoặc Quản trị viên.",
                        fontSize = 11.sp,
                        color = TextSecondary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 12.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            OutlinedButton(
                onClick = { applyServerAddress(); onDirectAnonymousAccess() },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentCyan)
            ) {
                Icon(Icons.Outlined.Inventory2, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text("Theo dõi tố giác đã gửi")
            }
            Text(
                "Xem tiến độ xử lý và trao đổi với Ban Thanh tra mà không cần đăng nhập.",
                fontSize = 11.sp,
                color = TextSecondary,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 6.dp, start = 8.dp, end = 8.dp)
            )

            Spacer(modifier = Modifier.height(20.dp))

            // Cấu hình máy chủ: chỉ bản debug (thử qua Wi-Fi chung). Bản release sau khi deploy ẩn hẳn.
            if (NetworkClient.allowServerEdit) {
                TextButton(onClick = { showConnectionSettings = !showConnectionSettings }) {
                    Icon(Icons.Outlined.Settings, contentDescription = null, tint = TextSecondary, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        if (showConnectionSettings) "Ẩn cài đặt kết nối" else "Cài đặt kết nối",
                        fontSize = 12.sp,
                        color = TextSecondary
                    )
                }
            }
            if (NetworkClient.allowServerEdit && showConnectionSettings) {
                val status = serverStatus
                OutlinedTextField(
                    value = serverInput,
                    onValueChange = { serverInput = it; errorMessage = null; serverStatus = null },
                    isError = (serverInput.isNotBlank() && ServerAddress.normalize(serverInput) == null) || status?.first == false,
                    label = { Text("Địa chỉ máy chủ") },
                    placeholder = { Text("vd. 192.168.1.38") },
                    // Nút kiểm tra nằm trong ô nhập để không bị bàn phím che; kết quả hiện ngay dưới ô
                    trailingIcon = {
                        if (checkingServer) {
                            CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = AccentCyan)
                        } else {
                            TextButton(onClick = checkServer) { Text("Kiểm tra", color = AccentCyan, fontSize = 13.sp) }
                        }
                    },
                    supportingText = {
                        Text(
                            status?.second ?: "Nhập IP máy chủ trong cùng mạng Wi-Fi rồi bấm Kiểm tra.",
                            fontSize = 11.sp,
                            color = when (status?.first) { true -> AccentGreen; false -> AccentRed; null -> TextSecondary }
                        )
                    },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { if (!checkingServer) checkServer() }),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    colors = fieldColors
                )
            }
        }
    }
}
