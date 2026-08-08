"""Phase 2 retention and deletion jobs.

These jobs are intentionally conservative: PostgreSQL remains the source of truth,
and object deletion is attempted before an asset is marked deleted. A failed object
store operation leaves the job failed and auditable for retry.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from accessforge.db.models import DeletionJob, MediaAsset
from accessforge.db.session import session_factory
from accessforge.jobs.celery_app import celery_app
from accessforge.storage.s3 import delete_object


async def _process_deletion_jobs() -> int:
    processed = 0
    async with session_factory() as session:
        jobs = list(
            (
                await session.scalars(
                    select(DeletionJob)
                    .where(DeletionJob.status == "queued")
                    .order_by(DeletionJob.requested_at.asc())
                    .limit(20)
                )
            ).all()
        )
        for job in jobs:
            job.status = "running"
            await session.flush()
            assets = list(
                (
                    await session.scalars(
                        select(MediaAsset).where(MediaAsset.project_id == job.project_id)
                    )
                ).all()
            )
            try:
                for asset in assets:
                    if asset.status != "deleted":
                        delete_object(object_key=asset.object_key)
                        asset.status = "deleted"
                        asset.updated_at = datetime.now(UTC)
                job.status = "succeeded"
                job.completed_at = datetime.now(UTC)
                processed += 1
            except Exception as exc:  # pragma: no cover - exercised by worker integration tests
                job.status = "failed"
                job.error = str(exc)[:1000]
            await session.commit()
    return processed


async def _expire_pending_assets() -> int:
    expired = 0
    now = datetime.now(UTC)
    async with session_factory() as session:
        assets = list(
            (
                await session.scalars(
                    select(MediaAsset).where(
                        MediaAsset.status == "pending", MediaAsset.expires_at < now
                    )
                )
            ).all()
        )
        for asset in assets:
            try:
                delete_object(object_key=asset.object_key)
            except Exception:
                # The object may never have been created. Keep the metadata state explicit.
                pass
            asset.status = "quarantined"
            asset.updated_at = now
            expired += 1
        await session.commit()
    return expired


@celery_app.task(name="accessforge.jobs.process_deletion_jobs")
def process_deletion_jobs() -> int:
    return asyncio.run(_process_deletion_jobs())


@celery_app.task(name="accessforge.jobs.expire_pending_assets")
def expire_pending_assets() -> int:
    return asyncio.run(_expire_pending_assets())


@celery_app.on_after_configure.connect  # type: ignore[misc]
def setup_periodic_tasks(sender: object, **_: object) -> None:
    """Run retention sweeps hourly when the worker is configured with beat."""
    sender.add_periodic_task(3600.0, expire_pending_assets.s(), name="expire pending uploads")  # type: ignore[attr-defined]
