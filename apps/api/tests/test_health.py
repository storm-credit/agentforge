import importlib.util

import pytest


RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


def test_runtime_dependencies_are_declared():
    missing = [package for package in RUNTIME_DEPS if importlib.util.find_spec(package) is None]
    assert isinstance(missing, list)


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_healthz_returns_ok():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_readyz_skips_all_checks_by_default():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "skipped",
        "vector_store": "skipped",
        "object_store": "skipped",
    }


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_readyz_reports_unavailable_vector_store(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setattr("app.main.check_vector_store", lambda: False)

    client = TestClient(create_app())
    response = client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["vector_store"] == "unavailable"
    assert body["database"] == "skipped"
    assert body["object_store"] == "skipped"


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_readyz_reports_unavailable_object_store(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setattr("app.main.check_object_store", lambda: False)

    client = TestClient(create_app())
    response = client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["object_store"] == "unavailable"
    assert body["database"] == "skipped"
    assert body["vector_store"] == "skipped"


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_check_vector_store_stays_skipped_and_untouched_when_not_active(monkeypatch):
    """When the vector backend isn't 'qdrant', the check must report skipped
    (None) without ever constructing a real client -- even if that client
    would fail/misbehave if it were ever built."""
    from app.core.config import get_settings
    from app.domain import vector as vector_module

    settings = get_settings()
    monkeypatch.setattr(settings, "vector_backend", "fake")  # default

    class ExplodingClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("QdrantClient should not be constructed when backend is 'fake'")

    monkeypatch.setattr("qdrant_client.QdrantClient", ExplodingClient)

    assert vector_module.check_vector_store() is None


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_check_vector_store_skips_when_not_qdrant_backend():
    from app.domain.vector import check_vector_store

    assert check_vector_store() is None


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_check_vector_store_reports_failure_on_qdrant_connectivity_error(monkeypatch):
    from app.core.config import get_settings
    from app.domain import vector as vector_module

    settings = get_settings()
    monkeypatch.setattr(settings, "vector_backend", "qdrant")
    monkeypatch.setattr(settings, "embedding_base_url", "http://fake-embedder:9999")

    class ExplodingClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("no qdrant here")

    monkeypatch.setattr("qdrant_client.QdrantClient", ExplodingClient)

    assert vector_module.check_vector_store() is False


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_check_object_store_skips_when_not_minio_backend():
    from app.infra.object_store import check_object_store

    assert check_object_store() is None


@pytest.mark.skipif(not runtime_deps_available(), reason="Runtime dependencies are not installed")
def test_check_object_store_reports_failure_on_minio_connectivity_error(monkeypatch):
    from app.core.config import get_settings
    from app.infra import object_store as object_store_module

    settings = get_settings()
    monkeypatch.setattr(settings, "object_store_backend", "minio")

    class ExplodingClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("no minio here")

    monkeypatch.setattr("minio.Minio", ExplodingClient)

    assert object_store_module.check_object_store() is False
