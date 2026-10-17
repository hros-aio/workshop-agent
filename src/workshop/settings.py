"""Application settings, loaded from environment via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKSHOP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://workshop:workshop@localhost:5432/hrms"
    db_schema: str = "workshop"

    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket: str = "workshop"
    s3_presign_ttl_seconds: int = 900
    s3_force_path_style: bool = True

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_audience: str | None = "hrms-platform"
    jwt_issuer: str | None = "hrms-auth"
    jwt_jwks_url: str | None = None

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_enabled: bool = False
    kafka_topic_prefix: str = "workshop"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    qwen_base_url: str = "http://localhost:8001/v1"
    qwen_api_key: str = "not-needed"
    qwen_model: str = "Qwen3.5-27B"

    duplicate_similarity_threshold: int = Field(default=90, ge=0, le=100)
    analysis_timeout_seconds: int = 600
    ai_max_retries: int = 1

    @property
    def kafka_exported_topic(self) -> str:
        return f"{self.kafka_topic_prefix}.exported"

    @property
    def kafka_finalized_topic(self) -> str:
        return f"{self.kafka_topic_prefix}.finalized"


@lru_cache
def get_settings() -> Settings:
    return Settings()
