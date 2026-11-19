package com.atbm.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import com.atbm.app.data.api.NetworkClient
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
    var serverUrl by remember { mutableStateOf(NetworkClient.getBaseUrl()) }
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

    val doLogin: () -> Unit = login@{
        if (employeeCode.isBlank() || password.isEmpty()) {
            errorMessage = "Vui lòng nhập mã nhân viên và mật khẩu."
            return@login
        }
        if (!NetworkClient.updateBaseUrl(serverUrl)) {
            showConnectionSettings = true
            errorMessage = "Địa chỉ máy chủ không hợp lệ. Địa chỉ phải bắt đầu bằng https://"
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
                onClick = onDirectAnonymousAccess,
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

            // Cấu hình máy chủ: ẩn mặc định, chỉ bộ phận kỹ thuật cần dùng khi triển khai.
            TextButton(onClick = { showConnectionSettings = !showConnectionSettings }) {
                Icon(Icons.Outlined.Settings, contentDescription = null, tint = TextSecondary, modifier = Modifier.size(16.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    if (showConnectionSettings) "Ẩn cài đặt kết nối" else "Cài đặt kết nối",
                    fontSize = 12.sp,
                    color = TextSecondary
                )
            }
            if (showConnectionSettings) {
                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = { serverUrl = it; errorMessage = null },
                    isError = serverUrl.isNotBlank() && !NetworkClient.isValidHttpsUrl(serverUrl),
                    label = { Text("Địa chỉ máy chủ") },
                    supportingText = { Text("Chỉ thay đổi khi được bộ phận kỹ thuật hướng dẫn.", fontSize = 11.sp) },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(10.dp),
                    colors = fieldColors
                )
            }
        }
    }
}
