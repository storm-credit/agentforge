"""Fail-fast boot validation for Settings' fixed-choice backend fields.

Each of vector_backend / object_store_backend / rerank_backend / judge_backend is
meant to be one of a small closed set of strings. Before this, they were typed as
plain `str`, so a typo (wrong case, misspelling) would silently construct a Settings
object that "looks" configured but actually falls through every `== "expected"`
check in the codebase -- the app boots green while quietly running on a fallback
nobody asked for. Literal[...] + a cross-field validator turn that into a loud
ValidationError at Settings() construction time (which happens at process import,
see app/main.py and app/core/database.py -- both call get_settings() at module
scope).
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


# ---------------------------------------------------------------------------
# Literal field validation: bad values rejected, good values accepted.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("vector_backend", "Qdrant"),  # wrong case
        ("vector_backend", "qdrnat"),  # typo
        ("object_store_backend", "s3"),  # not a supported backend
        ("object_store_backend", "Minio"),  # wrong case
        ("rerank_backend", "vllm"),  # not yet wired
        ("rerank_backend", "Hybrid_Lexical"),  # wrong case
        ("judge_backend", "gpt"),  # not a supported backend
        ("judge_backend", "LLM"),  # wrong case
    ],
)
def test_invalid_backend_literal_value_rejected(field, bad_value):
    kwargs = {field: bad_value}
    # vector_backend="qdrant"-shaped typos need an embedding_base_url set too, so the
    # failure we observe is specifically the Literal rejection, not the cross-field one.
    if field == "vector_backend":
        kwargs["embedding_base_url"] = "http://localhost:11434/v1"
    with pytest.raises(ValidationError, match=field):
        Settings(**kwargs)


@pytest.mark.parametrize(
    "field, good_value",
    [
        ("vector_backend", "fake"),
        ("vector_backend", "qdrant"),
        ("object_store_backend", "none"),
        ("object_store_backend", "memory"),
        ("object_store_backend", "minio"),
        ("rerank_backend", "none"),
        ("rerank_backend", "hybrid_lexical"),
        ("judge_backend", "none"),
        ("judge_backend", "llm"),
    ],
)
def test_valid_backend_literal_value_accepted(field, good_value):
    kwargs = {field: good_value}
    if field == "vector_backend" and good_value == "qdrant":
        kwargs["embedding_base_url"] = "http://localhost:11434/v1"
    Settings(**kwargs)  # must not raise


# ---------------------------------------------------------------------------
# Cross-field validator: vector_backend="qdrant" requires embedding_base_url.
# ---------------------------------------------------------------------------


def test_qdrant_backend_without_embedding_url_raises():
    with pytest.raises(ValidationError, match="AGENT_FORGE_VECTOR_BACKEND=qdrant"):
        Settings(vector_backend="qdrant", embedding_base_url=None)


def test_qdrant_backend_with_empty_embedding_url_raises():
    with pytest.raises(ValidationError, match="AGENT_FORGE_VECTOR_BACKEND=qdrant"):
        Settings(vector_backend="qdrant", embedding_base_url="")


def test_qdrant_backend_with_embedding_url_constructs_successfully():
    settings = Settings(vector_backend="qdrant", embedding_base_url="http://localhost:11434/v1")
    assert settings.vector_backend == "qdrant"


# ---------------------------------------------------------------------------
# Defaults must still work out of the box (local dev / hermetic CI).
# ---------------------------------------------------------------------------


def test_default_settings_construct_successfully():
    settings = Settings()
    assert settings.vector_backend == "fake"
    assert settings.object_store_backend == "none"
    assert settings.rerank_backend == "none"
    assert settings.judge_backend == "none"
