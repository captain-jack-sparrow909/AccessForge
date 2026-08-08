from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from accessforge.core.config import get_settings


def storage_client() -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
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


def head_object(*, object_key: str) -> dict[str, Any]:
    settings = get_settings()
    return storage_client().head_object(Bucket=settings.s3_bucket_private, Key=object_key)


def delete_object(*, object_key: str) -> None:
    settings = get_settings()
    storage_client().delete_object(Bucket=settings.s3_bucket_private, Key=object_key)
