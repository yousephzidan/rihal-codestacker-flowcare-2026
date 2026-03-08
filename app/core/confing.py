import os
from typing import ClassVar, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Replace the postgres username:password with yours.. 
    DATABASE_URL: str = "postgresql://flowcare:flowcare@localhost:5432/flowcare_db"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    UPLOAD_DIR: str = "../../uploads"
    MAX_FILE_SIZE_MB: int = 5
    ALLOWED_IMAGE_TYPES: ClassVar[List[str]] = ["image/jpeg", "image/png", "image/jpg"]
    ALLOWED_DOCUMENT_TYPES: ClassVar[List[str]] = ["application/pdf"]
    SOFT_DELETE_RETENTION_DAYS: int = 30
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def setup_directories():
    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "customer_ids"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "attachments"), exist_ok=True)

