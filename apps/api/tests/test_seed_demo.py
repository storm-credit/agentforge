import importlib.util
from collections.abc import Iterator

import pytest


RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)


@pytest.fixture
def db_session() -> Iterator:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base
    from app.domain import models  # noqa: F401

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)


def test_seed_creates_published_agent_and_indexed_chunks(db_session):
    from app.seed_demo import seed_demo

    result = seed_demo(db_session)
    assert result["agent_id"]
    assert result["agent_version_id"]
    assert result["source_id"]
    assert result["chunk_count"] >= 1
