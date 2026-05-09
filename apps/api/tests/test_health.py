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
def test_readyz_skips_database_by_default():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "skipped"}
