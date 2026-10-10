import os
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "EditFrames Video Generation Studio"
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_key: SecretStr | None = None
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    database_url: str = (
        "postgresql+asyncpg://screening:screening_dev_password@localhost:5432/screening"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=180)

    max_application_chars: int = Field(default=30000, ge=100, le=100000)
    task_max_retries: int = Field(default=2, ge=0, le=5)

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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def enforce_production_secrets(self):
        if self.environment == "production" and not self.api_key:
            raise ValueError("API_KEY is required when ENVIRONMENT=production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
