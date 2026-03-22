"""Application settings loaded from environment variables."""
from __future__ import annotations

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = secrets.token_urlsafe(32)
    DATABASE_URL: str = "sqlite:///./lesson_plan.db"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    UPLOAD_DIR: str = "tmp/uploads"
    PROJECT_ROOT: str = str(Path(__file__).resolve().parent.parent.parent)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
