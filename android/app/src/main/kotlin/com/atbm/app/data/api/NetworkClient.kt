package com.atbm.app.data.api

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
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

    private const val PREFS = "atbm_connection"
    private const val KEY_SERVER_URL = "server_url"

    /** Bản debug cho phép gõ địa chỉ máy chủ (thử qua Wi-Fi chung); bản release luôn dùng SERVER_URL. */
    val allowServerEdit: Boolean = com.atbm.app.BuildConfig.ALLOW_SERVER_EDIT

    /** Gọi một lần lúc mở app: nạp địa chỉ máy chủ đã lưu (chỉ bản debug). */
    fun init(context: Context) {
        if (!allowServerEdit) return
        val saved = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_SERVER_URL, null)
        if (saved != null) updateBaseUrl(saved)
    }

    /** Áp dụng + lưu địa chỉ máy chủ (không phải dữ liệu nhạy cảm: chỉ là IP/tên miền). */
    fun saveServerUrl(context: Context, url: String): Boolean {
        if (!updateBaseUrl(url)) return false
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_SERVER_URL, currentBaseUrl).apply()
        return true
    }

    /** Thử gọi GET /health của máy chủ; ném lỗi mạng/TLS nguyên bản để hiển thị thông báo thân thiện. */
    suspend fun checkServer(baseUrl: String): Boolean = withContext(Dispatchers.IO) {
        val client = OkHttpClient.Builder()
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(5, TimeUnit.SECONDS)
            .build()
        client.newCall(Request.Builder().url(baseUrl + "health").get().build()).execute().use { resp ->
            resp.isSuccessful && (resp.body?.string()?.contains("\"status\"") == true)
        }
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
        // Bản release: không cho đổi địa chỉ máy chủ lúc chạy (tránh bị lừa trỏ app về server giả)
        if (!allowServerEdit && formatted != DEFAULT_SERVER_URL) return false
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
