package com.atbm.app.data.api

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Quản lý kết nối mạng Retrofit tập trung cho ứng dụng Android ATBM.
 */
object NetworkClient {

    // Ngrok static domain cấu hình sẵn cho kết nối Internet / 4G / Wi-Fi từ xa
    private const val DEFAULT_NGROK_URL = "https://chas-unshaped-jacalyn.ngrok-free.dev/"
    
    private var currentBaseUrl: String = DEFAULT_NGROK_URL
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
     * Cập nhật URL máy chủ linh hoạt khi kết nối qua LAN / Thiết bị thật.
     */
    fun updateBaseUrl(newUrl: String) {
        val formatted = if (newUrl.endsWith("/")) newUrl else "$newUrl/"
        currentBaseUrl = formatted
        val (iApi, aApi) = buildApis(formatted)
        identifiedApi = iApi
        anonymousApi = aApi
    }

    fun getBaseUrl(): String = currentBaseUrl

    private fun buildApis(baseUrl: String): Pair<IdentifiedApi, AnonymousApi> {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val request = chain.request().newBuilder()
                    .addHeader("ngrok-skip-browser-warning", "true")
                    .build()
                chain.proceed(request)
            }
            .addInterceptor(logging)
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
