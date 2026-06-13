from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agent Forge API"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://agentforge:agentforge@localhost:5432/agentforge"
    readiness_check_database: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3300",
            "http://127.0.0.1:3300",
        ]
    )
    llm_base_url: str | None = None
    llm_model: str = "qwen3:8b"
    llm_timeout_seconds: float = 30.0
    llm_temperature: float = 0.2
    llm_top_p: float | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024
    embedding_timeout_seconds: float = 30.0
    qdrant_url: str = "http://localhost:6333"
    vector_backend: str = "fake"  # "fake" | "qdrant"
    retrieval_min_score: float = 0.0  # drop retrieval hits below this score (relevance gating)
    grounding_min: float = 0.0  # refuse answers grounded below this score (injection/hallucination guard)
    chunk_target_tokens: int = 320  # heading-bounded chunk size (eojeol proxy; ~650 subword tokens)
    chunk_overlap_tokens: int = 50  # sliding-window overlap between chunks (eojeol proxy; ~100 subword)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENT_FORGE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

