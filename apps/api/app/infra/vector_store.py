from __future__ import annotations

from app.core.config import Settings, get_settings
from app.domain.vector import FakeVectorStore, QdrantVectorStore, VectorStore


def get_vector_store(settings: Settings | None = None) -> VectorStore:
    resolved_settings = settings or get_settings()
    backend = resolved_settings.vector_store_backend.lower()

    if backend == "fake":
        return FakeVectorStore()

    if backend == "qdrant":
        return QdrantVectorStore(
            url=resolved_settings.qdrant_url,
            collection=resolved_settings.qdrant_collection,
            vector_size=resolved_settings.qdrant_vector_size,
            timeout_seconds=resolved_settings.qdrant_timeout_seconds,
        )

    raise ValueError(f"Unsupported vector store backend: {resolved_settings.vector_store_backend}")
