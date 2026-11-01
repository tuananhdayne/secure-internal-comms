from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.identified import User, Post, Comment
from app.schemas.posts import PostCreate, PostResponse, PostDetailResponse, CommentCreate, CommentResponse
from app.api.deps import get_current_user, require_role

router = APIRouter(tags=["Posts & Newsfeed"])


@router.get("", response_model=List[PostResponse])
def list_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[PostResponse]:
    """Xem danh sách bản tin nội bộ (Hỗ trợ phân loại và ghim bài viết lên đầu)."""
    query = db.query(Post).options(joinedload(Post.author))
    if category:
        query = query.filter(Post.category == category)

    posts = query.order_by(Post.is_pinned.desc(), Post.created_at.desc()).offset(skip).limit(limit).all()

    results: List[PostResponse] = []
    for p in posts:
        resp = PostResponse.model_validate(p)
        resp.author_name = p.author.full_name if p.author else "Hệ thống"
        results.append(resp)

    return results


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    post_in: PostCreate,
    current_user: User = Depends(require_role(["BOARD_DIRECTOR", "SYSTEM_ADMIN"])),
    db: Session = Depends(get_db)
) -> PostResponse:
    """Đăng bài viết mới trên mạng truyền thông nội bộ (Dành cho Ban Giám Đốc và Quản trị viên)."""
    new_post = Post(
        author_id=current_user.id,
        title=post_in.title.strip(),
        content=post_in.content.strip(),
        category=post_in.category,
        attachment_url=post_in.attachment_url,
        is_pinned=post_in.is_pinned
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    resp = PostResponse.model_validate(new_post)
    resp.author_name = current_user.full_name
    return resp


@router.get("/{post_id}", response_model=PostDetailResponse)
def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> PostDetailResponse:
    """Xem chi tiết bài viết kèm danh sách bình luận."""
    post = db.query(Post).options(
        joinedload(Post.author),
        joinedload(Post.comments).joinedload(Comment.author)
    ).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bài viết không tồn tại."
        )

    resp = PostDetailResponse.model_validate(post)
    resp.author_name = post.author.full_name if post.author else "Hệ thống"

    # Gán author_name cho từng comment
    for c_resp, c_model in zip(resp.comments, post.comments):
        c_resp.author_name = c_model.author.full_name if c_model.author else "Vô danh"

    return resp


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: int,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CommentResponse:
    """Thêm bình luận vào bài viết nội bộ."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bài viết không tồn tại."
        )

    new_comment = Comment(
        post_id=post_id,
        author_id=current_user.id,
        content=comment_in.content.strip()
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    resp = CommentResponse.model_validate(new_comment)
    resp.author_name = current_user.full_name
    return resp
