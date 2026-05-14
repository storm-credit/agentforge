from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Callable, Protocol
from urllib.parse import unquote, urlparse

from app.core.config import get_settings


class ObjectStorageError(RuntimeError):
    pass


class ObjectStorageNotFound(ObjectStorageError):
    pass


@dataclass(frozen=True)
class StoredObject:
    uri: str
    bucket: str
    key: str
    size_bytes: int


class ObjectStorage(Protocol):
    def put_bytes(self, *, key: str, content: bytes, content_type: str) -> StoredObject:
        ...

    def get_bytes(self, uri: str) -> bytes:
        ...


StorageProvider = Callable[[], ObjectStorage]


class LocalObjectStorage:
    def __init__(self, *, base_path: str | Path, bucket: str) -> None:
        self.base_path = Path(base_path)
        self.bucket = bucket

    def put_bytes(self, *, key: str, content: bytes, content_type: str) -> StoredObject:
        normalized_key = _normalize_key(key)
        path = self.base_path / self.bucket / Path(*PurePosixPath(normalized_key).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredObject(
            uri=_object_uri(self.bucket, normalized_key),
            bucket=self.bucket,
            key=normalized_key,
            size_bytes=len(content),
        )

    def get_bytes(self, uri: str) -> bytes:
        bucket, key = _parse_storage_uri(uri)
        path = self.base_path / bucket / Path(*PurePosixPath(key).parts)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectStorageNotFound(f"Object not found: {uri}") from exc
        except OSError as exc:
            raise ObjectStorageError(f"Could not read object: {uri}") from exc


class S3ObjectStorage:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region_name: str,
        access_key_id: str | None,
        secret_access_key: str | None,
        create_bucket: bool,
    ) -> None:
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise ObjectStorageError(
                "S3 object storage requires boto3. Install boto3 or use local storage."
            ) from exc

        self.bucket = bucket
        self.region_name = region_name
        self._client_error = ClientError
        self._create_bucket = create_bucket
        kwargs: dict[str, object] = {"region_name": region_name}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if access_key_id:
            kwargs["aws_access_key_id"] = access_key_id
        if secret_access_key:
            kwargs["aws_secret_access_key"] = secret_access_key
        kwargs["config"] = Config(s3={"addressing_style": "path"})
        self.client = boto3.client("s3", **kwargs)
        self._bucket_ready = False

    def put_bytes(self, *, key: str, content: bytes, content_type: str) -> StoredObject:
        normalized_key = _normalize_key(key)
        self._ensure_bucket()
        self.client.put_object(
            Bucket=self.bucket,
            Key=normalized_key,
            Body=content,
            ContentType=content_type,
        )
        return StoredObject(
            uri=_object_uri(self.bucket, normalized_key),
            bucket=self.bucket,
            key=normalized_key,
            size_bytes=len(content),
        )

    def get_bytes(self, uri: str) -> bytes:
        bucket, key = _parse_storage_uri(uri)
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except self._client_error as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "NoSuchBucket", "404"}:
                raise ObjectStorageNotFound(f"Object not found: {uri}") from exc
            raise ObjectStorageError(f"Could not read object: {uri}") from exc

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return

        try:
            self.client.head_bucket(Bucket=self.bucket)
        except self._client_error as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if not self._create_bucket or code not in {"404", "NoSuchBucket", "NotFound"}:
                raise ObjectStorageError(f"Object storage bucket is not available: {self.bucket}") from exc
            create_kwargs: dict[str, object] = {"Bucket": self.bucket}
            if self.region_name != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": self.region_name
                }
            self.client.create_bucket(**create_kwargs)

        self._bucket_ready = True


def get_object_storage_provider() -> StorageProvider:
    return get_object_storage


@lru_cache
def get_object_storage() -> ObjectStorage:
    settings = get_settings()
    backend = settings.object_storage_backend.lower()
    if backend == "local":
        return LocalObjectStorage(
            base_path=settings.object_storage_local_path,
            bucket=settings.object_storage_bucket,
        )
    if backend in {"s3", "minio"}:
        return S3ObjectStorage(
            bucket=settings.object_storage_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            create_bucket=settings.s3_create_bucket,
        )
    raise ObjectStorageError(f"Unsupported object storage backend: {settings.object_storage_backend}")


def _normalize_key(key: str) -> str:
    candidate = key.replace("\\", "/").strip("/")
    parts = [part for part in PurePosixPath(candidate).parts if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ObjectStorageError(f"Invalid object key: {key}")
    return "/".join(parts)


def _parse_storage_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme in {"object", "s3"}:
        bucket = parsed.netloc
        key = unquote(parsed.path.lstrip("/"))
    else:
        raise ObjectStorageError(f"Unsupported object URI: {uri}")

    if not bucket or not key:
        raise ObjectStorageError(f"Invalid object URI: {uri}")
    return bucket, _normalize_key(key)


def _object_uri(bucket: str, key: str) -> str:
    return f"object://{bucket}/{key}"
