package com.atbm.app.data.api

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

/**
 * Cụm 1: API Mạng truyền thông nội bộ & Cấp phát chữ ký mù (Yêu cầu JWT Bearer Token).
 */
interface IdentifiedApi {

    @FormUrlEncoded
    @POST("api/v1/auth/login")
    suspend fun login(
        @Field("username") employeeCode: String,
        @Field("password") password: String
    ): Response<TokenResponse>

    @GET("api/v1/auth/me")
    suspend fun getProfile(
        @Header("Authorization") bearerToken: String
    ): Response<UserProfile>

    @GET("api/v1/posts")
    suspend fun getPosts(
        @Header("Authorization") bearerToken: String
    ): Response<List<PostItem>>

    @GET("api/v1/posts/{id}")
    suspend fun getPostDetail(
        @Header("Authorization") bearerToken: String,
        @Path("id") postId: Int
    ): Response<PostItem>

    @POST("api/v1/posts/{id}/comments")
    suspend fun addComment(
        @Header("Authorization") bearerToken: String,
        @Path("id") postId: Int,
        @Body req: CreateCommentRequest
    ): Response<CommentItem>

    @GET("api/v1/compliance/public-keys")
    suspend fun getOfficerPublicKeys(
        @Header("Authorization") bearerToken: String
    ): Response<OfficerKeysResponse>

    @POST("api/v1/compliance/blind-sign")
    suspend fun requestBlindSign(
        @Header("Authorization") bearerToken: String,
        @Body req: BlindSignRequest
    ): Response<BlindSignResponse>
}
