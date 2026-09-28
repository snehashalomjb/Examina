"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


def parse_cors_origins(v: Any) -> list[str]:
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        if v.startswith("[") and v.endswith("]"):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    if isinstance(v, (list, tuple, set)):
        return [str(item).strip() for item in v if str(item).strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "AI-Based Intelligent Examination Platform"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: Annotated[list[str] | str, BeforeValidator(parse_cors_origins)] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )


    # Database
    DATABASE_URL: str = "postgresql+psycopg://exam:exam@localhost:5433/examdb"
    TEST_DATABASE_URL: str = "postgresql+psycopg://exam:exam@localhost:5434/examdb_test"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    SQL_ECHO: bool = False

    # Security
    SECRET_KEY: str = "dev-only-secret-key-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EXAM_SESSION_TOKEN_EXPIRE_MINUTES: int = 15
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Object storage
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "exam-media"
    S3_REGION: str = "us-east-1"
    S3_PRESIGN_EXPIRE_SECONDS: int = 900
    STORAGE_ENABLED: bool = True

    # Grading
    GRADER_PROVIDER: str = "stub"
    GRADER_MODEL: str = "gpt-4o"
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # Question/exam translation (auto-translate "Generate Translations" button)
    TRANSLATION_PROVIDER: str = "stub"
    TRANSLATION_MODEL: str = "gpt-4o-mini"
    TRANSLATION_API_KEY: str | None = None

    # OCR (handwritten answer scans)
    #: Absolute path to the tesseract binary. Only needed when it is not on PATH -
    #: the usual case on Windows: C:/Program Files/Tesseract-OCR/tesseract.exe
    TESSERACT_CMD: str | None = None
    OCR_LANGUAGES: str = "eng"
    #: Run OCR at upload time. Turn off to keep uploads fast on a box without Tesseract.
    OCR_ENABLED: bool = True

    # Bootstrap
    FIRST_ADMIN_EMAIL: str = "admin@exam.edu"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(PROJECT_ROOT / "logs")

    @property
    def log_path(self) -> Path:
        p = Path(self.LOG_DIR)
        if not p.is_absolute():
            p = (BACKEND_DIR / p).resolve()
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
