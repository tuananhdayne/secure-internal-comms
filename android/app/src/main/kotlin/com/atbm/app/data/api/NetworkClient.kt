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

    // 10.0.2.2 là địa chỉ IP máy chủ host đối với Android Emulator
    private const val DEFAULT_EMULATOR_URL = "http://10.0.2.2:8000/"
    
    private var currentBaseUrl: String = DEFAULT_EMULATOR_URL
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
