import pytest

from app.core.config import get_settings
from app.domain.vector import FakeVectorStore, get_vector_store


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_backend_is_fake(monkeypatch):
    # setenv (not delenv): OS env overrides the .env file, so the test is
    # hermetic whether or not a live .env is present.
    monkeypatch.setenv("AGENT_FORGE_VECTOR_BACKEND", "fake")
    assert isinstance(get_vector_store(), FakeVectorStore)


def test_qdrant_backend_without_embedding_url_fails_fast_at_boot(monkeypatch):
    """Previously this silently fell back to FakeVectorStore -- a deployment that
    explicitly asked for qdrant would boot "healthy" while quietly running on the
    in-memory fake. A cross-field validator now rejects this combination loudly at
    Settings() construction time instead."""
    monkeypatch.setenv("AGENT_FORGE_VECTOR_BACKEND", "qdrant")
    # empty string overrides any .env value and is falsy -> validator must reject it
    monkeypatch.setenv("AGENT_FORGE_EMBEDDING_BASE_URL", "")
    with pytest.raises(Exception, match="AGENT_FORGE_VECTOR_BACKEND=qdrant"):
        get_vector_store()


def test_qdrant_backend_with_config_returns_qdrant(monkeypatch):
    monkeypatch.setenv("AGENT_FORGE_VECTOR_BACKEND", "qdrant")
    monkeypatch.setenv("AGENT_FORGE_EMBEDDING_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("AGENT_FORGE_QDRANT_URL", "http://localhost:6333")
    from app.infra.qdrant_store import QdrantVectorStore

    assert isinstance(get_vector_store(), QdrantVectorStore)
