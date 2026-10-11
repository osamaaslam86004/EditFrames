import os
from functools import lru_cache
from typing import Annotated, Literal

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import (
    BaseModel,
    PostgresDsn,
    RedisDsn,
    HttpUrl,
    SecretStr,
    Field,
    field_validator,
    model_validator,
)


# 1. Define Sub-Configs using standard BaseModel
class AppConfig(BaseModel):
    app_name: str = "Video Generation Studio With Kokoro"
    description: str = (
        "Multi-tenant scheduling backend for video generation and processing"
    )
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    dashboard_url: str = "http://localhost:8000/dashboard"

    @model_validator(mode="after")
    def enforce_production_secrets(self):
        if self.environment == "production" and not self.api_key:
            raise ValueError("API_KEY is required when ENVIRONMENT=production")
        return self


# Security Configurations
class SecurityConfig(BaseModel):
    # secret_key: str
    # session_secret: str
    # algorithm: str = "HS256"
    api_key: SecretStr | None = (None,)
    front_end_url: HttpUrl = Field(default="http://localhost:3000")
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    allow_credentials: bool = True
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


# Database Configurations
class DatabaseConfig(BaseModel):
    async_url: PostgresDsn
    sync_url: PostgresDsn
    pool_size: int = 20
    max_overflow: int = 10


# Redis Configurations
class RedisConfig(BaseModel):
    base_url: RedisDsn = Field(alias="url")
    sync_db: int = 0
    async_db: int = 1
    socket_connect_timeout: int = (15,)
    socket_timeout: int = (5,)
    dlq_key: str = Field(
        default="calendar_tasks:dead_letter",
        description="Key used for pushing dead letter queue payloads",
    )

    @property
    def url(self) -> str:
        """
        # Constructs a standard Redis connection URL.
        Wehn to Use: celery_tasks, sync_background_workers, cli_scripts

        # Constructs a standard Redis connection URL string.
        """
        # Convert DSN to string and strip trailing slashes or existing DB numbers
        raw_url = (
            str(self.base_url).rsplit("/", 1)[0]
            if str(self.base_url).count("/") > 2
            else str(self.base_url).rstrip("/")
        )
        return f"{raw_url}/{self.sync_db}"

    @property
    def async_url(self) -> str:
        """
        # Constructs an async Redis connection URL if using redis-py async features.
        Wehn to Use: FastAPI route handlers, Asyncio background loops

        # Constructs an async Redis connection URL string.
        """
        raw_url = (
            str(self.base_url).rsplit("/", 1)[0]
            if str(self.base_url).count("/") > 2
            else str(self.base_url).rstrip("/")
        )
        return f"{raw_url}/{self.async_db}"


# Celery Configurations
class CeleryConfig(BaseModel):
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    task_max_retries: int = Field(default=2, ge=0, le=5)


# LLM Provider Configurations
class LLMModelProviderConfig(BaseModel):
    gemini_api_key: SecretStr = Field(..., description="Google Gemini API Key")
    gemini_model: str = "gemini-2.5-flash"
    llm_base_url: str | None = None
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=180)

    # Add hf_token with alias matching HF__TOKEN from your .env
    hf_token: SecretStr | None = Field(
        default=None,
        alias="hf_token",
        validation_alias="HF__TOKEN",
        description="HuggingFace API Token",
    )

    max_application_chars: int = Field(default=30000, ge=100, le=100000)

    @field_validator("gemini_api_key")
    @classmethod
    def validate_api_keys(cls, v: SecretStr) -> SecretStr:
        raw_key = v.get_secret_value().strip()
        if not raw_key or len(raw_key) < 10:
            raise ValueError("API Key appears invalid or too short.")
        return v


class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    security: SecurityConfig
    db: DatabaseConfig
    redis: RedisConfig
    celery: CeleryConfig
    llm: LLMModelProviderConfig

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Uses '__' to map env vars to nested fields (e.g., DB__URL maps to settings.db.url)
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def base_dir(self) -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @property
    def videos_dir(self) -> str:
        path = os.path.join(self.base_dir, "videos")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def static_dir(self) -> str:
        path = os.path.join(self.base_dir, "static")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def template_path(self) -> str:
        return os.path.join(self.base_dir, "template.html")


@lru_cache
def get_settings() -> Settings:
    return Settings()
