package com.atbm.app

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.atbm.app.ui.screens.LoginScreen
import com.atbm.app.ui.screens.NewsfeedScreen
import com.atbm.app.ui.screens.VaultScreen
import com.atbm.app.ui.screens.WhistleblowerScreen
import com.atbm.app.ui.theme.AtbmTheme
import com.atbm.app.ui.theme.BgDark

/**
 * Main Activity của ứng dụng ATBM Secure Communications & Whistleblower Engine.
 * 
 * NGUYÊN TẮC BẢO MẬT & HARDENING:
 * 1. Bật FLAG_SECURE ở cấp Window: Ngăn chặn Android chụp ảnh màn hình, quay video màn hình
 *    hoặc lưu thumbnail trong Task Switcher gần đây.
 * 2. Quản lý trạng thái chuyển đổi màn hình type-safe trong Jetpack Compose.
 */
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // CHỐNG CHỤP / QUAY MÀN HÌNH (ANTI-SCREENSHOT HARDENING)
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )

        // Khởi tạo Notification Channel
        com.atbm.app.domain.notification.CaseNotificationManager.initChannel(this)

        setContent {
            AtbmTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = BgDark
                ) {
                    AppNavigationRoot()
                }
            }
        }
    }
}

sealed class Screen {
    object Login : Screen()
    data class Newsfeed(val token: String, val role: String, val employeeCode: String) : Screen()
    data class Whistleblower(val token: String) : Screen()
    object Vault : Screen()
}

@Composable
fun AppNavigationRoot() {
    var currentScreen by remember { mutableStateOf<Screen>(Screen.Login) }
    var userToken by remember { mutableStateOf("") }
    var userRole by remember { mutableStateOf("") }
    var userEmpCode by remember { mutableStateOf("") }

    when (val s = currentScreen) {
        is Screen.Login -> {
            LoginScreen(
                onLoginSuccess = { token, role, empCode ->
                    userToken = token
                    userRole = role
                    userEmpCode = empCode
                    currentScreen = Screen.Newsfeed(token, role, empCode)
                },
                onDirectAnonymousAccess = {
                    currentScreen = Screen.Vault
                }
            )
        }

        is Screen.Newsfeed -> {
            NewsfeedScreen(
                token = s.token,
                employeeCode = s.employeeCode,
                role = s.role,
                onNavigateToWhistleblower = {
                    currentScreen = Screen.Whistleblower(s.token)
                },
                onNavigateToVault = {
                    currentScreen = Screen.Vault
                },
                onLogout = {
                    userToken = ""
                    currentScreen = Screen.Login
                }
            )
        }

        is Screen.Whistleblower -> {
            WhistleblowerScreen(
                token = s.token,
                onNavigateBack = {
                    currentScreen = Screen.Newsfeed(userToken, userRole, userEmpCode)
                },
                onSubmissionSuccess = { _ ->
                    currentScreen = Screen.Vault
                }
            )
        }

        is Screen.Vault -> {
            VaultScreen(
                onNavigateBack = {
                    if (userToken.isNotEmpty()) {
                        currentScreen = Screen.Newsfeed(userToken, userRole, userEmpCode)
                    } else {
                        currentScreen = Screen.Login
                    }
                },
                onPanicWiped = {
                    // Khi kích hoạt Panic PIN: Xóa sạch phiên và chuyển về màn hình đăng nhập
                    userToken = ""
                    userRole = ""
                    userEmpCode = ""
                    currentScreen = Screen.Login
                }
            )
        }
    }
}
