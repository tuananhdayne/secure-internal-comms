package com.atbm.app.data.api

import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Quản lý kết nối mạng Retrofit tập trung cho ứng dụng Android ATBM.
 */
object NetworkClient {

    // Địa chỉ máy chủ lấy từ cấu hình lúc build (gradle property `atbm.serverUrl`, xem app/build.gradle.kts).
    // Không dùng dịch vụ tunnel công cộng (ngrok...) để tránh lộ metadata kết nối cho bên thứ ba.
    private val DEFAULT_SERVER_URL: String = com.atbm.app.BuildConfig.SERVER_URL

    private var currentBaseUrl: String = DEFAULT_SERVER_URL
    private var retrofit: Retrofit? = null

    var identifiedApi: IdentifiedApi
        private set
    var anonymousApi: AnonymousApi
        private set

    init {
        val (iApi, aApi) = buildApis(currentBaseUrl)
        identifiedApi = iApi
        anonymousApi = aApi
    }

    /**
     * Cập nhật URL máy chủ (LAN / thiết bị thật). Chỉ chấp nhận HTTPS: mọi kết nối bắt buộc qua TLS
     * (network_security_config.xml cũng cấm cleartext ở tầng hệ điều hành).
     * @return false nếu URL không hợp lệ hoặc không phải https:// (giữ nguyên URL cũ).
     */
    fun updateBaseUrl(newUrl: String): Boolean {
        val trimmed = newUrl.trim()
        if (!isValidHttpsUrl(trimmed)) return false
        val formatted = if (trimmed.endsWith("/")) trimmed else "$trimmed/"
        if (formatted == currentBaseUrl) return true
        currentBaseUrl = formatted
        val (iApi, aApi) = buildApis(formatted)
        identifiedApi = iApi
        anonymousApi = aApi
        return true
    }

    fun getBaseUrl(): String = currentBaseUrl

    fun isValidHttpsUrl(url: String): Boolean {
        val parsed = url.trim().toHttpUrlOrNull() ?: return false
        return parsed.isHttps && parsed.host.isNotBlank()
    }

    private fun buildApis(baseUrl: String): Pair<IdentifiedApi, AnonymousApi> {
        val okHttpClient = OkHttpClient.Builder()
            // KHÔNG gắn HttpLoggingInterceptor: log BODY sẽ ghi mật khẩu, JWT và dữ liệu hồ sơ ra logcat.
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .build()

        val r = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        retrofit = r
        return Pair(
            r.create(IdentifiedApi::class.java),
            r.create(AnonymousApi::class.java)
        )
    }
}
