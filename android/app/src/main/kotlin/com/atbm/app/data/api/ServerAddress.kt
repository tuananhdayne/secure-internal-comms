package com.atbm.app.data.api

import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/**
 * Chuẩn hóa địa chỉ máy chủ người dùng gõ ở "Cài đặt kết nối" (chỉ bản debug — thử qua Wi-Fi chung).
 *
 *   "192.168.1.38"            -> https://192.168.1.38:8443/
 *   "192.168.1.38:9000"       -> https://192.168.1.38:9000/
 *   "https://api.vd.vn"       -> https://api.vd.vn/         (có scheme thì giữ cổng mặc định 443)
 *   "http://..."              -> null (cấm cleartext)
 */
object ServerAddress {

    /** Cổng của server dev (`./dev.sh run-https` / `./dev.sh lan`). */
    const val DEV_PORT: Int = 8443

    private val EXPLICIT_PORT = Regex(":(\\d{1,5})$")

    fun normalize(input: String): String? {
        val raw = input.trim().removeSuffix("/")
        if (raw.isEmpty() || raw.contains(' ')) return null
        val lower = raw.lowercase()
        val hasScheme = lower.startsWith("https://")
        if (!hasScheme && lower.contains("://")) return null  // http://, ftp://... — chỉ chấp nhận https
        val withScheme = if (hasScheme) raw else "https://$raw"
        val parsed = withScheme.toHttpUrlOrNull() ?: return null
        if (!parsed.isHttps || parsed.host.isBlank()) return null
        val authority = withScheme.substringAfter("://").substringBefore('/')
        val port = when {
            EXPLICIT_PORT.containsMatchIn(authority) -> parsed.port
            hasScheme -> parsed.port          // https://ten-mien -> 443
            else -> DEV_PORT                   // chỉ gõ IP -> cổng server dev
        }
        return HttpUrl.Builder().scheme("https").host(parsed.host).port(port).build().toString()
    }

    /** Dạng ngắn để hiện trong ô nhập: bỏ https:// và cổng 8443 mặc định. */
    fun display(baseUrl: String): String {
        val url = baseUrl.toHttpUrlOrNull() ?: return baseUrl
        return when (url.port) {
            DEV_PORT -> url.host
            443 -> "https://${url.host}"
            else -> "${url.host}:${url.port}"
        }
    }
}
