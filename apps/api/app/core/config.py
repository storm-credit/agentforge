from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
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
    llm_api_key: str | None = None  # optional bearer token for the LLM gateway (in-house/prod gateways may require auth); default None = no Authorization header sent
    embedding_base_url: str | None = None
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024
    embedding_timeout_seconds: float = 30.0
    embedding_api_key: str | None = None  # optional bearer token for the embedding gateway; default None = no Authorization header sent
    qdrant_url: str = "http://localhost:6333"
    vector_backend: Literal["fake", "qdrant"] = "fake"
    retrieval_min_score: float = 0.0  # drop retrieval hits below this score (relevance gating)
    answer_min_score: float = 0.0  # refuse (don't answer) if top hit scores below this — answer-confidence gate, separate from retrieval gate
    grounding_min: float = 0.0  # refuse answers grounded below this score (injection/hallucination guard)
    chunk_target_tokens: int = 320  # heading-bounded chunk size (eojeol proxy; ~650 subword tokens)
    chunk_overlap_tokens: int = 50  # sliding-window overlap between chunks (eojeol proxy; ~100 subword)
    pii_masking_enabled: bool = False  # regex-redact PII in answer + returned chunk content (default off)
    object_store_backend: Literal["none", "memory", "minio"] = "none"  # AF-009: original upload bytes
    object_store_endpoint: str | None = None
    object_store_access_key: str = "agentforge"
    object_store_secret_key: str = "agentforge-local"
    object_store_bucket: str = "agentforge"
    object_store_secure: bool = False
    rerank_backend: Literal["none", "hybrid_lexical"] = "none"  # hybrid_lexical = BM25+RRF, no model — see research-reranking-options.md. (A future vllm cross-encoder backend would be added here as a new literal value; get_reranker()'s warn-and-fallback branch for backends it doesn't recognize stays as defense-in-depth for direct settings mutation, e.g. in tests.)
    rerank_top_k: int | None = Field(default=None, ge=1)  # post-rerank cutoff: only the best-K reranked hits become context/citations; hits beyond K keep RetrievalHit rows with used_in_context=False (retrieval stays auditable). None (default) = unbounded — every surviving hit is used, exactly the pre-cutoff behavior. Pairs with retrieval_min_score: loosening the score gate only makes sense with a cutoff, or extra low-relevance hits flow straight into context/citations.
    judge_backend: Literal["none", "llm"] = "none"  # llm = LLM answerability judge (refusal discipline); runs on local Ollama

    @model_validator(mode="after")
    def _validate_vector_backend_requires_embedding_url(self) -> "Settings":
        if self.vector_backend == "qdrant" and not self.embedding_base_url:
            raise ValueError(
                "AGENT_FORGE_VECTOR_BACKEND=qdrant requires AGENT_FORGE_EMBEDDING_BASE_URL to be set "
                "(otherwise the app would silently fall back to the in-memory FakeVectorStore)"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AGENT_FORGE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

