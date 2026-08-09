from typing import Protocol, cast

import boto3
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

    def delete_object(self, *, Bucket: str, Key: str) -> object: ...


def storage_client() -> S3Client:
    settings = get_settings()
    return cast(
        S3Client,
        boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
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


def delete_object(*, object_key: str) -> None:
    settings = get_settings()
    storage_client().delete_object(Bucket=settings.s3_bucket_private, Key=object_key)
