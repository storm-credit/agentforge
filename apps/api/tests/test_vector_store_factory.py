import pytest

from app.core.config import Settings
from app.domain.vector import FakeVectorStore, QdrantVectorStore
from app.infra.vector_store import get_vector_store


def test_vector_store_factory_defaults_to_fake_adapter():
    store = get_vector_store(Settings())

    assert isinstance(store, FakeVectorStore)


def test_vector_store_factory_builds_qdrant_adapter_from_settings():
    store = get_vector_store(
        Settings(
            vector_store_backend="qdrant",
            qdrant_url="http://qdrant:6333",
            qdrant_collection="agentforge-test",
            qdrant_vector_size=32,
            qdrant_timeout_seconds=1.5,
        )
    )

    assert isinstance(store, QdrantVectorStore)
    assert store.url == "http://qdrant:6333"
    assert store.collection == "agentforge-test"
    assert store.vector_size == 32
    assert store.timeout_seconds == 1.5


def test_vector_store_factory_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unsupported vector store backend"):
        get_vector_store(Settings(vector_store_backend="unknown"))
