from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Cấu hình toàn hệ thống Secure Internal Comms & Whistleblower Engine."""

    PROJECT_NAME: str = "Secure Internal Comms & Whistleblower Engine"
    API_V1_STR: str = "/api/v1"

    # Database: Luôn trỏ tới file app.db trong thư mục backend để nhất quán mọi nơi
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/app.db"

    # JWT Authentication
    JWT_SECRET_KEY: str = "secure_internal_comms_secret_key_2026_defense"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Anti-spam Quota (Số lượt xin chữ ký mù tối đa/tuần của 1 nhân viên)
    WEEKLY_BLIND_SIGN_QUOTA: int = 5

    # Keys & Storage paths
    KEYS_DIR: str = str(BASE_DIR / "keys")
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def keys_path(self) -> Path:
        p = Path(self.KEYS_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        (p / "evidences").mkdir(parents=True, exist_ok=True)
        (p / "docs").mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
