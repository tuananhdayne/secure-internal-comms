from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class CommentCreate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime
    author_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    title: str
    content: str
    category: str = "GENERAL"
    attachment_url: Optional[str] = None
    is_pinned: bool = False


class PostResponse(BaseModel):
    id: int
    author_id: Optional[int]
    title: str
    content: str
    category: str
    attachment_url: Optional[str]
    is_pinned: bool
    created_at: datetime
    author_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostDetailResponse(PostResponse):
    comments: List[CommentResponse] = []
