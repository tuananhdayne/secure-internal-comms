import logging
from sqlalchemy.orm import Session

from app.db.session import engine, SessionLocal, Base
from app.models.identified import User, Post, Comment
from app.models.anonymous import WhistleCase, CaseEvidence, CaseMessage  # noqa: F401
from app.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_USERS = [
    {
        "employee_code": "NV001",
        "raw_password": "employee123",
        "full_name": "Nguyễn Văn An",
        "department": "Nghiên cứu & Phát triển (R&D)",
        "role": "EMPLOYEE"
    },
    {
        "employee_code": "NV002",
        "raw_password": "employee123",
        "full_name": "Trần Thị Bình",
        "department": "Tài chính - Kế toán",
        "role": "EMPLOYEE"
    },
    {
        "employee_code": "TT001",
        "raw_password": "officer123",
        "full_name": "Lê Thanh Tra",
        "department": "Ban Thanh tra & Tuân thủ",
        "role": "COMPLIANCE_OFFICER"
    },
    {
        "employee_code": "GD001",
        "raw_password": "director123",
        "full_name": "Phạm Giám Đốc",
        "department": "Ban Giám Đốc",
        "role": "BOARD_DIRECTOR"
    },
    {
        "employee_code": "AD001",
        "raw_password": "admin123",
        "full_name": "Hoàng Quản Trị",
        "department": "Phòng An toàn An ninh Mạng",
        "role": "SYSTEM_ADMIN"
    }
]

DEFAULT_POSTS = [
    {
        "author_code": "GD001",
        "title": "Chính sách An Toàn Thông Tin & Bảo vệ Người Tố Giác 2026",
        "content": (
            "Kính gửi toàn thể Cán bộ - Công nhân viên,\n\n"
            "Ban Giám Đốc ban hành chính sách bảo vệ tuyệt đối tính ẩn danh cho nhân viên phản ánh sai phạm. "
            "Mọi hồ sơ gửi qua Kênh Tố Giác Ẩn danh đều áp dụng chữ ký mù RSA và mã hóa đầu-cuối E2EE, "
            "không ai (kể cả IT hay Ban Giám Đốc) có thể truy vết danh tính người gửi.\n\n"
            "Trân trọng,\nBan Giám Đốc."
        ),
        "category": "ANNOUNCEMENT",
        "is_pinned": True
    },
    {
        "author_code": "AD001",
        "title": "Thông báo Nâng cấp Hệ thống Xác thực Sinh trắc học & Bảo mật Mobile",
        "content": (
            "Phòng IT Security đã triển khai phiên bản Android App mới tích hợp Room SQLCipher "
            "và cơ chế Panic PIN khẩn cấp nhằm bảo vệ người dùng trước các rủi ro bị ép buộc mở ứng dụng."
        ),
        "category": "SECURITY",
        "is_pinned": False
    },
    {
        "author_code": "NV001",
        "title": "Khảo sát Ý kiến Cải tiến Môi trường Làm việc Quý 4",
        "content": "Kính mời anh chị em phòng R&D và các phòng ban đóng góp ý kiến về cơ sở vật chất và quy trình làm việc.",
        "category": "GENERAL",
        "is_pinned": False
    }
]


def seed_database(db: Session) -> None:
    """Nạp dữ liệu mẫu ban đầu một cách idempotent."""
    # 1. Seed Users
    created_users = {}
    for user_data in DEFAULT_USERS:
        existing = db.query(User).filter(User.employee_code == user_data["employee_code"]).first()
        if not existing:
            new_user = User(
                employee_code=user_data["employee_code"],
                password_hash=get_password_hash(user_data["raw_password"]),
                full_name=user_data["full_name"],
                department=user_data["department"],
                role=user_data["role"],
                is_active=True
            )
            db.add(new_user)
            db.flush()
            created_users[user_data["employee_code"]] = new_user
            logger.info(f"Đã tạo user: {user_data['employee_code']} ({user_data['role']})")
        else:
            created_users[user_data["employee_code"]] = existing

    db.commit()

    # 2. Seed Posts
    for post_data in DEFAULT_POSTS:
        existing_post = db.query(Post).filter(Post.title == post_data["title"]).first()
        if not existing_post:
            author = created_users.get(post_data["author_code"])
            author_id = author.id if author else None

            new_post = Post(
                author_id=author_id,
                title=post_data["title"],
                content=post_data["content"],
                category=post_data["category"],
                is_pinned=post_data["is_pinned"]
            )
            db.add(new_post)
            db.flush()

            # Thêm bình luận mẫu
            comment = Comment(
                post_id=new_post.id,
                author_id=created_users["NV002"].id,
                content="Nhân viên đã nắm rõ quy định và rất ủng hộ chính sách bảo vệ ẩn danh này!"
            )
            db.add(comment)
            logger.info(f"Đã tạo bài viết: '{post_data['title']}'")

    db.commit()
    logger.info("Hoàn tất nạp dữ liệu mẫu thành công!")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_database(session)
