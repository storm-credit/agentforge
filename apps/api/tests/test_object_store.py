import pytest

from app.infra.object_store import (
    InMemoryObjectStore,
    ObjectNotFound,
    document_object_key,
)


def test_put_get_roundtrip():
    store = InMemoryObjectStore()
    store.put("documents/d1/source", b"hello bytes")
    assert store.get("documents/d1/source") == b"hello bytes"


def test_exists():
    store = InMemoryObjectStore()
    assert store.exists("k") is False
    store.put("k", b"x")
    assert store.exists("k") is True


def test_get_missing_raises_object_not_found():
    store = InMemoryObjectStore()
    with pytest.raises(ObjectNotFound):
        store.get("nope")


def test_document_object_key_is_traversal_safe():
    key = document_object_key("11111111-2222-3333-4444-555555555555")
    assert key == "documents/11111111-2222-3333-4444-555555555555/source"
    assert ".." not in key
