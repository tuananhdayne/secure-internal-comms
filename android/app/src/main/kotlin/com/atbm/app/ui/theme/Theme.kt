package com.atbm.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val BgDark = Color(0xFF0F172A)
val CardDark = Color(0xFF1E293B)
val BorderDark = Color(0xFF334155)
val TextPrimary = Color(0xFFF8FAFC)
val TextSecondary = Color(0xFF94A3B8)

val AccentCyan = Color(0xFF06B6D4)
val AccentBlue = Color(0xFF3B82F6)
val AccentGreen = Color(0xFF10B981)
val AccentRed = Color(0xFFEF4444)
val AccentAmber = Color(0xFFF59E0B)

private val DarkColorScheme = darkColorScheme(
    primary = AccentCyan,
    onPrimary = Color(0xFF0F172A),
    primaryContainer = Color(0xFF0E7490),
    secondary = AccentBlue,
    onSecondary = Color.White,
    background = BgDark,
    surface = CardDark,
    onBackground = TextPrimary,
    onSurface = TextPrimary,
    error = AccentRed,
    onError = Color.White
)

@Composable
fun AtbmTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
