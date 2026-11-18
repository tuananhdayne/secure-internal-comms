package com.atbm.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material.icons.outlined.PushPin
import androidx.compose.material.icons.outlined.RecordVoiceOver
import androidx.compose.material.icons.outlined.Newspaper
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.atbm.app.data.api.CreateCommentRequest
import com.atbm.app.data.api.NetworkClient
import com.atbm.app.data.api.PostItem
import com.atbm.app.domain.notification.CaseNotificationManager
import com.atbm.app.ui.components.DisplayText
import com.atbm.app.ui.components.DynamicWatermarkBox
import com.atbm.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NewsfeedScreen(
    token: String,
    employeeCode: String,
    role: String,
    onNavigateToWhistleblower: () -> Unit,
    onNavigateToVault: () -> Unit,
    onLogout: () -> Unit
) {
    val context = LocalContext.current
    var posts by remember { mutableStateOf<List<PostItem>>(emptyList()) }
    var selectedPost by remember { mutableStateOf<PostItem?>(null) }
    var newCommentText by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var unreadVaultCount by remember { mutableStateOf(0) }

    val scope = rememberCoroutineScope()

    val fetchPosts = {
        scope.launch {
            isLoading = true
            errorMessage = null
            try {
                val resp = NetworkClient.identifiedApi.getPosts("Bearer $token")
                if (resp.isSuccessful) {
                    posts = resp.body() ?: emptyList()
                } else {
                    errorMessage = if (resp.code() == 401) "Phiên đăng nhập đã hết hạn. Vui lòng đăng xuất và đăng nhập lại." else "Không thể tải bảng tin lúc này. Vui lòng thử lại."
                }
            } catch (e: Exception) {
                errorMessage = DisplayText.networkError(e)
            } finally {
                isLoading = false
            }
        }
    }

    val syncNotifications = {
        scope.launch {
            try {
                unreadVaultCount = CaseNotificationManager.checkCaseUpdates(context)
            } catch (_: Exception) {}
        }
    }

    LaunchedEffect(Unit) {
        fetchPosts()
        syncNotifications()
    }

    // Bọc toàn bộ bảng tin trong Dynamic Watermark Box
    DynamicWatermarkBox(
        employeeCode = employeeCode,
        fullName = "Nhân viên $employeeCode"
    ) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text(
                                text = "Bảng tin",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            Text(
                                text = "Xin chào, $employeeCode · ${DisplayText.role(role)}",
                                fontSize = 11.sp,
                                color = AccentCyan
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = CardDark),
                    actions = {
                        IconButton(onClick = onNavigateToVault) {
                            BadgedBox(
                                badge = {
                                    if (unreadVaultCount > 0) {
                                        Badge(
                                            containerColor = Color(0xFFEF4444),
                                            contentColor = Color.White
                                        ) {
                                            Text("$unreadVaultCount", fontSize = 9.sp, fontWeight = FontWeight.Bold)
                                        }
                                    }
                                }
                            ) {
                                Icon(Icons.Outlined.Inventory2, contentDescription = "Tố giác của tôi", tint = TextPrimary)
                            }
                        }
                        IconButton(onClick = onLogout) {
                            Icon(Icons.AutoMirrored.Outlined.Logout, contentDescription = "Đăng xuất", tint = TextPrimary)
                        }
                    }
                )
            },
            floatingActionButton = {
                ExtendedFloatingActionButton(
                    onClick = onNavigateToWhistleblower,
                    containerColor = AccentCyan,
                    contentColor = Color(0xFF0F172A),
                    icon = { Icon(Icons.Outlined.RecordVoiceOver, contentDescription = null) },
                    text = { Text("Gửi tố giác", fontWeight = FontWeight.SemiBold) }
                )
            },
            containerColor = BgDark
        ) { padding ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.align(Alignment.Center),
                        color = AccentCyan
                    )
                } else if (errorMessage != null) {
                    Column(
                        modifier = Modifier
                            .align(Alignment.Center)
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(text = errorMessage ?: "", color = AccentRed, fontSize = 14.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { fetchPosts() }) {
                            Text("Thử lại")
                        }
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 96.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        if (unreadVaultCount > 0) {
                            item {
                                Surface(
                                    color = Color(0xFFEF4444).copy(alpha = 0.15f),
                                    shape = RoundedCornerShape(10.dp),
                                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFEF4444).copy(alpha = 0.4f)),
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { onNavigateToVault() }
                                ) {
                                    Row(
                                        modifier = Modifier.padding(12.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Icon(Icons.Outlined.NotificationsActive, contentDescription = null, tint = Color(0xFFFCA5A5), modifier = Modifier.padding(end = 10.dp))
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = "Có phản hồi mới từ Ban Thanh tra",
                                                fontSize = 13.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = Color(0xFFFCA5A5)
                                            )
                                            Text(
                                                text = "$unreadVaultCount tố giác của bạn vừa được cập nhật. Nhấn để xem chi tiết.",
                                                fontSize = 11.sp,
                                                color = TextPrimary
                                            )
                                        }
                                        Icon(Icons.Outlined.ChevronRight, contentDescription = null, tint = Color(0xFFFCA5A5))
                                    }
                                }
                            }
                        }
                        if (posts.isEmpty()) {
                            item {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(top = 64.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Icon(Icons.Outlined.Newspaper, contentDescription = null, tint = TextSecondary, modifier = Modifier.size(48.dp))
                                    Spacer(modifier = Modifier.height(12.dp))
                                    Text("Chưa có thông báo nào", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                                    Text("Tin tức và thông báo của công ty sẽ hiển thị tại đây.", fontSize = 12.sp, color = TextSecondary)
                                }
                            }
                        }
                        items(posts) { post ->
                            PostCard(
                                post = post,
                                onClick = { selectedPost = post }
                            )
                        }
                    }
                }

                // Chi tiết bài viết Modal Dialog
                if (selectedPost != null) {
                    val currentPost = selectedPost!!
                    AlertDialog(
                        onDismissRequest = { selectedPost = null },
                        confirmButton = {
                            Button(onClick = { selectedPost = null }) {
                                Text("Đóng")
                            }
                        },
                        title = {
                            Text(
                                text = currentPost.title,
                                fontWeight = FontWeight.Bold,
                                fontSize = 16.sp
                            )
                        },
                        text = {
                            Column(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = "${currentPost.authorName ?: "Ban Giám đốc"} • ${DisplayText.serverDateTime(currentPost.createdAt)}",
                                    fontSize = 11.sp,
                                    color = TextSecondary
                                )
                                Spacer(modifier = Modifier.height(12.dp))
                                Text(
                                    text = currentPost.content,
                                    fontSize = 14.sp,
                                    color = TextPrimary
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                HorizontalDivider(color = BorderDark)
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = "Bình luận (${currentPost.comments?.size ?: 0})",
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 13.sp
                                )

                                val commentList = currentPost.comments ?: emptyList()
                                if (commentList.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(6.dp))
                                    commentList.takeLast(3).forEach { c ->
                                        Text(
                                            text = "• ${c.authorName}: ${c.content}",
                                            fontSize = 12.sp,
                                            color = TextPrimary,
                                            modifier = Modifier.padding(vertical = 2.dp)
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(8.dp))
                                OutlinedTextField(
                                    value = newCommentText,
                                    onValueChange = { newCommentText = it },
                                    placeholder = { Text("Viết bình luận...") },
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedTextColor = TextPrimary,
                                        unfocusedTextColor = TextPrimary
                                    )
                                )
                                Spacer(modifier = Modifier.height(6.dp))
                                Button(
                                    onClick = {
                                        if (newCommentText.isNotBlank()) {
                                            scope.launch {
                                                try {
                                                    val resp = NetworkClient.identifiedApi.addComment(
                                                        "Bearer $token",
                                                        currentPost.id,
                                                        CreateCommentRequest(newCommentText.trim())
                                                    )
                                                    if (!resp.isSuccessful) {
                                                        android.widget.Toast.makeText(context, "Không gửi được bình luận. Vui lòng thử lại.", android.widget.Toast.LENGTH_SHORT).show()
                                                    }
                                                    if (resp.isSuccessful) {
                                                        newCommentText = ""
                                                        val detailResp = NetworkClient.identifiedApi.getPostDetail("Bearer $token", currentPost.id)
                                                        if (detailResp.isSuccessful && detailResp.body() != null) {
                                                            selectedPost = detailResp.body()
                                                        }
                                                        fetchPosts()
                                                    }
                                                } catch (e: Exception) {
                                                    android.widget.Toast.makeText(context, DisplayText.networkError(e), android.widget.Toast.LENGTH_SHORT).show()
                                                }
                                            }
                                        }
                                    },
                                    modifier = Modifier.align(Alignment.End)
                                ) {
                                    Text("Gửi bình luận")
                                }
                            }
                        },
                        containerColor = CardDark
                    )
                }
            }
        }
    }
}

@Composable
fun PostCard(post: PostItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = CardDark),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = post.title,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary,
                    modifier = Modifier.weight(1f)
                )
                if (post.isPinned) {
                    Surface(
                        color = AccentAmber.copy(alpha = 0.2f),
                        shape = RoundedCornerShape(4.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Icon(Icons.Outlined.PushPin, contentDescription = null, tint = AccentAmber, modifier = Modifier.size(12.dp))
                            Spacer(modifier = Modifier.width(3.dp))
                            Text(text = "Đã ghim", color = AccentAmber, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = post.content,
                fontSize = 13.sp,
                color = TextSecondary,
                maxLines = 2
            )

            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "${post.authorName ?: "Ban Giám đốc"} • ${DisplayText.serverDateTime(post.createdAt)}",
                    fontSize = 11.sp,
                    color = AccentCyan
                )
                Text(
                    text = "${post.comments?.size ?: 0} bình luận",
                    fontSize = 11.sp,
                    color = TextSecondary
                )
            }
        }
    }
}
