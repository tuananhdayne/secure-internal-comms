package com.atbm.app.data.api

import com.google.gson.annotations.SerializedName

// --- CỤM 1: ĐỊNH DANH & TRUYỀN THÔNG NỘI BỘ ---

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type") val tokenType: String,
    @SerializedName("role") val role: String
)

data class UserProfile(
    @SerializedName("id") val id: Int,
    @SerializedName("employee_code") val employeeCode: String,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("department") val department: String,
    @SerializedName("role") val role: String
)

data class CommentItem(
    @SerializedName("id") val id: Int,
    @SerializedName("author_name") val authorName: String,
    @SerializedName("content") val content: String,
    @SerializedName("created_at") val createdAt: String
)

data class PostItem(
    @SerializedName("id") val id: Int,
    @SerializedName("title") val title: String,
    @SerializedName("content") val content: String,
    @SerializedName("author_name") val authorName: String,
    @SerializedName("is_pinned") val isPinned: Boolean,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("comments") val comments: List<CommentItem> = emptyList()
)

data class CreateCommentRequest(
    @SerializedName("content") val content: String
)

data class BlindSignPublicKeyInfo(
    @SerializedName("e") val e: String,
    @SerializedName("n") val n: String
)

data class OfficerKeysResponse(
    @SerializedName("blind_sign_pub") val blindSignPub: BlindSignPublicKeyInfo,
    @SerializedName("chat_pub_hex") val chatPubHex: String
)

data class BlindSignRequest(
    @SerializedName("blinded_hash") val blindedHash: String
)

data class BlindSignResponse(
    @SerializedName("blind_signature") val blindSignature: String
)


// --- CỤM 2: CỔNG TỐ GIÁC SAI PHẠM ẨN DANH & CHAT E2EE ---

data class CaseSubmitResponse(
    @SerializedName("case_token") val caseToken: String,
    @SerializedName("status") val status: String,
    @SerializedName("message") val message: String
)

data class CaseMessageItem(
    @SerializedName("id") val id: Int,
    @SerializedName("sender_role") val senderRole: String, // "WHISTLEBLOWER" hoặc "OFFICER"
    @SerializedName("ephemeral_public_key") val ephemeralPublicKey: String,
    @SerializedName("iv") val iv: String,
    @SerializedName("ciphertext") val ciphertext: String,
    @SerializedName("auth_tag") val authTag: String,
    @SerializedName("sender_signature") val senderSignature: String?,
    @SerializedName("created_at") val createdAt: String
)

data class CaseDetailResponse(
    @SerializedName("case_token") val caseToken: String,
    @SerializedName("status") val status: String,
    @SerializedName("category") val category: String,
    @SerializedName("created_bucket") val createdBucket: String,
    @SerializedName("messages") val messages: List<CaseMessageItem> = emptyList()
)

data class SendMessageRequest(
    @SerializedName("ephemeral_public_key") val ephemeralPublicKey: String,
    @SerializedName("iv") val iv: String,
    @SerializedName("ciphertext") val ciphertext: String,
    @SerializedName("auth_tag") val authTag: String,
    @SerializedName("sender_signature") val senderSignature: String
)
