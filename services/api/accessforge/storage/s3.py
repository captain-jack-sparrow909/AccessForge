from dataclasses import dataclass
from typing import Protocol, cast

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from accessforge.core.config import get_settings


class S3Client(Protocol):
    """Narrow typed boundary around the untyped boto3 S3 client."""

    def head_bucket(self, *, Bucket: str) -> object: ...

    def create_bucket(self, *, Bucket: str) -> object: ...

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict[str, object],
        ExpiresIn: int,
        HttpMethod: str,
    ) -> str: ...

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
        ContentLength: int,
    ) -> object: ...

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]: ...

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]: ...

    def delete_object(self, *, Bucket: str, Key: str) -> object: ...

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str,
        MaxKeys: int,
        ContinuationToken: str | None = None,
    ) -> dict[str, object]: ...


@dataclass(frozen=True)
class PrivateObjectListing:
    """A bounded project-prefix inventory used by deletion reconciliation."""

    keys: tuple[str, ...]
    complete: bool


def storage_client() -> S3Client:
    settings = get_settings()
    # Keep one S3 request inside the deletion worker's 60-second defensive
    # timeout. The durable deletion outbox, rather than botocore, owns retry
    # timing and records only sanitized failure categories.
    request_config = Config(
        connect_timeout=settings.s3_connect_timeout_seconds,
        read_timeout=settings.s3_read_timeout_seconds,
        retries={"mode": "standard", "total_max_attempts": 1},
    )
    return cast(
        S3Client,
        boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=request_config,
        ),
    )


def ensure_private_bucket() -> None:
    settings = get_settings()
    client = storage_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket_private)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket_private)
    except BotoCoreError:
        raise


def presign_upload(*, object_key: str, content_type: str, content_length: int) -> str:
    settings = get_settings()
    return storage_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket_private,
            "Key": object_key,
            "ContentType": content_type,
            "ContentLength": content_length,
        },
        ExpiresIn=settings.asset_presign_ttl_seconds,
        HttpMethod="PUT",
    )


def presign_download(*, object_key: str) -> str:
    settings = get_settings()
    return storage_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_private, "Key": object_key},
        ExpiresIn=settings.asset_presign_ttl_seconds,
        HttpMethod="GET",
    )


def put_private_bytes(*, object_key: str, content: bytes, content_type: str) -> None:
    """Persist a server-produced immutable artifact in the private bucket."""

    settings = get_settings()
    ensure_private_bucket()
    storage_client().put_object(
        Bucket=settings.s3_bucket_private,
        Key=object_key,
        Body=content,
        ContentType=content_type,
        ContentLength=len(content),
    )


def head_object(*, object_key: str) -> dict[str, object]:
    settings = get_settings()
    return storage_client().head_object(Bucket=settings.s3_bucket_private, Key=object_key)


def get_private_bytes(*, object_key: str, max_bytes: int = 50_000_000) -> bytes:
    """Read a server-produced private object for hash verification/packaging.

    Callers must still verify the immutable database checksum and size.  This
    intentionally has no user-controlled bucket or key input and bounds the
    in-memory read before an export ZIP is assembled.
    """

    if max_bytes < 1:
        raise ValueError("The private object read limit must be positive.")
    settings = get_settings()
    response = storage_client().get_object(Bucket=settings.s3_bucket_private, Key=object_key)
    body = response.get("Body")
    reader = getattr(body, "read", None)
    if not callable(reader):
        raise ValueError("The private object response is missing its body.")
    content = reader(max_bytes + 1)
    if not isinstance(content, bytes):
        raise ValueError("The private object body is invalid.")
    if len(content) > max_bytes:
        raise ValueError("The private object exceeds the export read limit.")
    return content


def delete_object(*, object_key: str) -> None:
    settings = get_settings()
    storage_client().delete_object(Bucket=settings.s3_bucket_private, Key=object_key)


def list_project_private_object_keys(
    *, project_id: str, max_keys: int = 1_000
) -> PrivateObjectListing:
    """List a bounded fixed project prefix without accepting an arbitrary path."""

    if max_keys < 1:
        raise ValueError("The project object listing limit must be positive.")
    settings = get_settings()
    client = storage_client()
    prefix = f"private/{project_id}/"
    keys: list[str] = []
    continuation_token: str | None = None
    while len(keys) < max_keys:
        remaining = max_keys - len(keys)
        if continuation_token is None:
            response = client.list_objects_v2(
                Bucket=settings.s3_bucket_private,
                Prefix=prefix,
                MaxKeys=remaining,
            )
        else:
            response = client.list_objects_v2(
                Bucket=settings.s3_bucket_private,
                Prefix=prefix,
                MaxKeys=remaining,
                ContinuationToken=continuation_token,
            )
        contents = response.get("Contents")
        if isinstance(contents, list):
            for item in contents:
                if not isinstance(item, dict):
                    continue
                key = item.get("Key")
                if isinstance(key, str) and key.startswith(prefix):
                    keys.append(key)
        truncated = response.get("IsTruncated") is True
        if not truncated:
            return PrivateObjectListing(keys=tuple(keys), complete=True)
        next_token = response.get("NextContinuationToken")
        if not isinstance(next_token, str) or not next_token:
            return PrivateObjectListing(keys=tuple(keys), complete=False)
        continuation_token = next_token
    return PrivateObjectListing(keys=tuple(keys), complete=False)
