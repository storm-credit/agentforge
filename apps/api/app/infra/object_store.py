"""Object storage abstraction for original document bytes (AF-009).

The app reads/writes original upload bytes through this interface so the index
worker can fetch content from storage instead of requiring it inline on the request.
Deterministic ``InMemoryObjectStore`` backs tests and the local default; a lazy
``MinioObjectStore`` (S3-compatible) is used in real deployments.

Keys are derived from the document id (a UUID), never from user-supplied filenames,
so there is no path-traversal surface.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol


class ObjectNotFound(KeyError):
    """Raised when a key is absent from the store."""


def document_object_key(document_id: str) -> str:
    """Deterministic, traversal-safe storage key for a document's original bytes."""
    return f"documents/{document_id}/source"


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class InMemoryObjectStore:
    """Process-local store. Used by tests and the local 'memory' backend."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self._data[key] = bytes(data)

    def get(self, key: str) -> bytes:
        if key not in self._data:
            raise ObjectNotFound(key)
        return self._data[key]

    def exists(self, key: str) -> bool:
        return key in self._data


class MinioObjectStore:
    """S3-compatible store backed by MinIO. ``minio`` is imported lazily so the
    dependency is only required when this backend is actually selected."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        from minio import Minio  # lazy

        self._bucket = bucket
        self._client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def put(self, key: str, data: bytes) -> None:
        import io

        self._client.put_object(self._bucket, key, io.BytesIO(data), length=len(data))

    def get(self, key: str) -> bytes:
        from minio.error import S3Error

        try:
            response = self._client.get_object(self._bucket, key)
        except S3Error as exc:  # noqa: BLE001 - normalize to our not-found
            raise ObjectNotFound(key) from exc
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        from minio.error import S3Error

        try:
            self._client.stat_object(self._bucket, key)
            return True
        except S3Error:
            return False


@lru_cache
def get_object_store() -> ObjectStore | None:
    """Return the configured object store, or ``None`` when disabled (default).

    ``None`` preserves the pre-AF-009 behavior (uploads handled inline, queued jobs
    without inline content fail closed).
    """
    from app.core.config import get_settings

    settings = get_settings()
    backend = settings.object_store_backend
    if backend == "memory":
        return InMemoryObjectStore()
    if backend == "minio":
        return MinioObjectStore(
            endpoint=settings.object_store_endpoint or "localhost:9000",
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key,
            bucket=settings.object_store_bucket,
            secure=settings.object_store_secure,
        )
    return None
