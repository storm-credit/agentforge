from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agent Forge API"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://agentforge:agentforge@localhost:5432/agentforge"
    readiness_check_database: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    object_storage_backend: str = "local"
    object_storage_bucket: str = "agent-forge-documents"
    object_storage_local_path: str = ".agentforge/object-storage"
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_create_bucket: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENT_FORGE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

