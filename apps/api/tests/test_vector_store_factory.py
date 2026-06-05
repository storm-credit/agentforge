import pytest

from app.core.config import get_settings
from app.domain.vector import FakeVectorStore, get_vector_store


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_backend_is_fake(monkeypatch):
    monkeypatch.delenv("AGENT_FORGE_VECTOR_BACKEND", raising=False)
    assert isinstance(get_vector_store(), FakeVectorStore)


def test_qdrant_backend_without_embedding_url_falls_back_to_fake(monkeypatch):
    monkeypatch.setenv("AGENT_FORGE_VECTOR_BACKEND", "qdrant")
    monkeypatch.delenv("AGENT_FORGE_EMBEDDING_BASE_URL", raising=False)
    assert isinstance(get_vector_store(), FakeVectorStore)


def test_qdrant_backend_with_config_returns_qdrant(monkeypatch):
    monkeypatch.setenv("AGENT_FORGE_VECTOR_BACKEND", "qdrant")
    monkeypatch.setenv("AGENT_FORGE_EMBEDDING_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("AGENT_FORGE_QDRANT_URL", "http://localhost:6333")
    from app.infra.qdrant_store import QdrantVectorStore

    assert isinstance(get_vector_store(), QdrantVectorStore)
