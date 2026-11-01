package com.atbm.app.data.api

import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

/**
 * Cụm 2: Cổng tố giác sai phạm ẩn danh (Zero-Knowledge Endpoint).
 * Tuyệt đối không gửi header Authorization hay định danh nhân viên.
 */
interface AnonymousApi {

    @Multipart
    @POST("api/v1/anonymous/cases")
    suspend fun submitCase(
        @Part("category") category: RequestBody,
        @Part("encrypted_title") encryptedTitle: RequestBody,
        @Part("encrypted_description") encryptedDescription: RequestBody,
        @Part("payload_ephemeral_pub") payloadEphemeralPub: RequestBody,
        @Part("payload_iv") payloadIv: RequestBody,
        @Part("payload_auth_tag") payloadAuthTag: RequestBody,
        @Part("case_token") caseToken: RequestBody,
        @Part("case_public_key") casePublicKey: RequestBody,
        @Part("unblinded_signature") unblindedSignature: RequestBody,
        @Part files: List<MultipartBody.Part>
    ): Response<CaseSubmitResponse>

    @GET("api/v1/anonymous/cases/{case_token}")
    suspend fun getCaseStatus(
        @Path("case_token") caseToken: String
    ): Response<CaseDetailResponse>

    @POST("api/v1/anonymous/cases/{case_token}/messages")
    suspend fun sendMessage(
        @Path("case_token") caseToken: String,
        @Body req: SendMessageRequest
    ): Response<CaseMessageItem>
}
