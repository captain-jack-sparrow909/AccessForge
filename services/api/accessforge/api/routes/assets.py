from datetime import UTC, datetime, timedelta

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.config import get_settings
from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import AuditEvent, ConsentRecord, MediaAsset, utc_now
from accessforge.db.session import get_session
from accessforge.projects.workflow import get_owned_project
from accessforge.storage.s3 import (
    ensure_private_bucket,
    head_object,
    presign_download,
    presign_upload,
)

router = APIRouter(prefix="/v1/projects/{project_id}/assets", tags=["assets"])

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "still_image",
    "image/png": "still_image",
    "image/webp": "still_image",
    "video/mp4": "video",
    "video/webm": "video",
}


class AssetPresignRequest(BaseModel):
    media_type: str = Field(pattern="^(still_image|video)$")
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(gt=0)
    original_name: str | None = Field(default=None, max_length=255)


class AssetPresignResponse(BaseModel):
    asset_id: str
    upload_url: str
    expires_at: datetime
    object_key: str
    max_size_bytes: int


class AssetCompleteRequest(BaseModel):
    actual_size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(pattern="^[a-fA-F0-9]{64}$")


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    media_type: str
    content_type: str
    original_name: str | None
    expected_size: int
    actual_size: int | None
    checksum_sha256: str | None
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    version: int


class AssetDownloadResponse(BaseModel):
    asset: AssetRead
    download_url: str
    expires_at: datetime


async def require_media_consent(session: AsyncSession, project_id: str, media_type: str) -> None:
    consent_type = "still_images" if media_type == "still_image" else "video"
    granted = await session.scalar(
        select(ConsentRecord.id)
        .where(
            ConsentRecord.project_id == project_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.granted.is_(True),
            ConsentRecord.revoked_at.is_(None),
        )
        .limit(1)
    )
    if granted is None:
        readable_consent_type = consent_type.replace("_", " ")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(f"Separate consent for {readable_consent_type} is required before upload."),
        )


@router.get("", response_model=list[AssetRead])
async def list_assets(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[MediaAsset]:
    project = await get_owned_project(session, principal, project_id)
    result = await session.scalars(
        select(MediaAsset)
        .where(MediaAsset.project_id == project.id, MediaAsset.status != "deleted")
        .order_by(MediaAsset.created_at.asc())
    )
    return list(result.all())


@router.post("/presign-upload", response_model=AssetPresignResponse)
async def presign_asset_upload(
    project_id: str,
    payload: AssetPresignRequest,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> AssetPresignResponse:
    project = await get_owned_project(session, principal, project_id)
    settings = get_settings()
    expected_media_type = ALLOWED_CONTENT_TYPES.get(payload.content_type.lower())
    if expected_media_type != payload.media_type:
        raise HTTPException(
            status_code=422,
            detail="The media type does not match the allowlisted content type.",
        )
    if payload.size_bytes > settings.asset_max_bytes:
        raise HTTPException(status_code=413, detail="This file exceeds the upload size limit.")
    await require_media_consent(session, project.id, payload.media_type)
    from uuid import uuid4

    object_key = f"private/{project.id}/{uuid4().hex}"
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.asset_presign_ttl_seconds)
    try:
        ensure_private_bucket()
        upload_url = presign_upload(
            object_key=object_key,
            content_type=payload.content_type.lower(),
            content_length=payload.size_bytes,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail="Object storage is not available.") from exc
    asset = MediaAsset(
        project_id=project.id,
        object_key=object_key,
        media_type=payload.media_type,
        content_type=payload.content_type.lower(),
        original_name=payload.original_name,
        expected_size=payload.size_bytes,
        expires_at=expires_at,
    )
    session.add(asset)
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="asset.upload_presigned",
            reason="A time-limited upload URL was issued.",
            details={"asset_id": asset.id, "media_type": asset.media_type},
        )
    )
    await session.commit()
    return AssetPresignResponse(
        asset_id=asset.id,
        upload_url=upload_url,
        expires_at=expires_at,
        object_key=object_key,
        max_size_bytes=settings.asset_max_bytes,
    )


@router.post("/{asset_id}/complete", response_model=AssetRead)
async def complete_asset_upload(
    project_id: str,
    asset_id: str,
    payload: AssetCompleteRequest,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> MediaAsset:
    project = await get_owned_project(session, principal, project_id)
    asset = await session.scalar(
        select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.project_id == project.id)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset.status != "pending":
        raise HTTPException(status_code=409, detail="This upload is no longer pending.")
    asset.actual_size = payload.actual_size_bytes
    asset.checksum_sha256 = payload.checksum_sha256.lower()
    expires_at = asset.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    remote_size: int | None = None
    remote_content_type: str | None = None
    try:
        remote_metadata = head_object(object_key=asset.object_key)
        remote_size = int(remote_metadata.get("ContentLength", -1))
        remote_content_type = str(remote_metadata.get("ContentType", ""))
    except (BotoCoreError, ClientError):
        remote_size = None
    if (
        expires_at < datetime.now(UTC)
        or payload.actual_size_bytes != asset.expected_size
        or remote_size != asset.expected_size
        or remote_content_type != asset.content_type
    ):
        asset.status = "quarantined"
        reason = "Upload metadata did not match the presigned request, object, or expiry window."
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id=principal.subject,
                event_type="asset.quarantined",
                reason=reason,
                details={"asset_id": asset.id},
            )
        )
        await session.commit()
        raise HTTPException(status_code=422, detail=reason)
    asset.status = "uploaded"
    asset.updated_at = utc_now()
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="asset.upload_completed",
            reason="Upload metadata matched the presigned request.",
            details={"asset_id": asset.id},
        )
    )
    await session.commit()
    await session.refresh(asset)
    return asset


@router.get("/{asset_id}/download", response_model=AssetDownloadResponse)
async def download_asset(
    project_id: str,
    asset_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> AssetDownloadResponse:
    project = await get_owned_project(session, principal, project_id)
    asset = await session.scalar(
        select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.project_id == project.id)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset.status != "uploaded":
        raise HTTPException(status_code=409, detail="This asset is not available for download.")
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.asset_presign_ttl_seconds)
    try:
        download_url = presign_download(object_key=asset.object_key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status_code=503, detail="Object storage is not available.") from exc
    return AssetDownloadResponse(
        asset=AssetRead.model_validate(asset), download_url=download_url, expires_at=expires_at
    )
