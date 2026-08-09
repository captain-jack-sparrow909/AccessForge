"""Phase 2 retention and deletion jobs.

These jobs are intentionally conservative: PostgreSQL remains the source of truth,
and object deletion is attempted before an asset is marked deleted. A failed object
store operation leaves the job failed and auditable for retry.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select, update

from accessforge.cad.service import process_cad_candidate
from accessforge.db.models import (
    AuditEvent,
    CadJob,
    CandidateArtifact,
    CandidateDesign,
    DeletionJob,
    MediaAsset,
    Project,
)
from accessforge.db.results import affected_row_count
from accessforge.db.session import session_factory
from accessforge.jobs.celery_app import celery_app
from accessforge.planning.service import reconcile_comparison_batch
from accessforge.projects.workflow import transition_project
from accessforge.storage.s3 import delete_object

CAD_RECOVERY_BATCH_LIMIT = 100
CAD_RUNNING_STALE_AFTER = timedelta(minutes=20)


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
                candidate_artifacts = list(
                    (
                        await session.scalars(
                            select(CandidateArtifact).where(
                                CandidateArtifact.project_id == job.project_id
                            )
                        )
                    ).all()
                )
                for asset in assets:
                    if asset.status != "deleted":
                        delete_object(object_key=asset.object_key)
                        asset.status = "deleted"
                        asset.updated_at = datetime.now(UTC)
                for artifact in candidate_artifacts:
                    delete_object(object_key=artifact.object_key)
                    await session.delete(artifact)
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


async def _recover_cad_jobs() -> dict[str, int]:
    """Durably dispatch queued jobs and terminally resolve stale worker claims.

    The database is the outbox: candidate and job rows are committed before a
    broker publish is attempted. Repeated dispatch is safe because the worker
    must atomically claim a queued job before compilation.
    """

    now = datetime.now(UTC)
    stale_before = now - CAD_RUNNING_STALE_AFTER
    dispatch_ids: list[str] = []
    stale_failed = 0
    async with session_factory() as session:
        stale_jobs = list(
            (
                await session.scalars(
                    select(CadJob)
                    .where(
                        CadJob.status == "running",
                        CadJob.started_at.is_not(None),
                        CadJob.started_at < stale_before,
                    )
                    .order_by(CadJob.started_at.asc())
                    .limit(CAD_RECOVERY_BATCH_LIMIT)
                )
            ).all()
        )
        for job in stale_jobs:
            candidate = await session.get(CandidateDesign, job.candidate_id)
            if candidate is None:
                continue
            project = await session.get(Project, candidate.project_id)
            if project is None:
                continue
            # The two durable rows must change together.  A savepoint keeps a
            # competing worker completion from leaving a candidate terminal
            # while its job remains running (or vice versa).
            recovery_attempt = await session.begin_nested()
            cancellation_won = (
                candidate.status in {"cancel_requested", "cancelled"}
                or job.cancel_requested_at is not None
            )
            if cancellation_won:
                candidate_terminal = await session.execute(
                    update(CandidateDesign)
                    .where(
                        CandidateDesign.id == candidate.id,
                        CandidateDesign.status.in_({"running", "cancel_requested", "cancelled"}),
                    )
                    .values(
                        status="cancelled",
                        failure_category=None,
                        failure_detail=None,
                        completed_at=now,
                    )
                )
                if affected_row_count(candidate_terminal) != 1:
                    await recovery_attempt.rollback()
                    continue
                job_terminal = await session.execute(
                    update(CadJob)
                    .execution_options(synchronize_session=False)
                    .where(
                        CadJob.id == job.id,
                        CadJob.status == "running",
                        CadJob.started_at.is_not(None),
                        CadJob.started_at < stale_before,
                    )
                    .values(status="cancelled", cancelled_at=now, completed_at=now)
                )
                if affected_row_count(job_terminal) != 1:
                    await recovery_attempt.rollback()
                    continue
                event_type = "candidate.worker_cancellation_recovered"
                event_reason = (
                    "A stale CAD worker claim was cancelled after its durable cooperative "
                    "cancellation request outlived the worker."
                )
            else:
                candidate_terminal = await session.execute(
                    update(CandidateDesign)
                    .where(CandidateDesign.id == candidate.id, CandidateDesign.status == "running")
                    .values(
                        status="failed",
                        failure_category="worker_lease_expired",
                        failure_detail=(
                            "The worker claim exceeded the bounded recovery window before a "
                            "complete private artifact bundle was persisted."
                        ),
                        completed_at=now,
                    )
                )
                if affected_row_count(candidate_terminal) != 1:
                    await recovery_attempt.rollback()
                    continue
                job_terminal = await session.execute(
                    update(CadJob)
                    .execution_options(synchronize_session=False)
                    .where(
                        CadJob.id == job.id,
                        CadJob.status == "running",
                        CadJob.started_at.is_not(None),
                        CadJob.started_at < stale_before,
                    )
                    .values(
                        status="failed",
                        failure_category="worker_lease_expired",
                        failure_detail=(
                            "The worker claim exceeded the bounded recovery window "
                            "before completion."
                        ),
                        completed_at=now,
                    )
                )
                if affected_row_count(job_terminal) != 1:
                    await recovery_attempt.rollback()
                    continue
                stale_failed += 1
                event_type = "candidate.worker_lease_expired"
                event_reason = (
                    "A stale CAD worker claim was marked failed without retrying an uncertain "
                    "compilation attempt."
                )
            if candidate.generation_batch_id is not None:
                await reconcile_comparison_batch(
                    session,
                    project=project,
                    batch_id=candidate.generation_batch_id,
                    actor_id="system:cad-recovery",
                )
            elif project.status == "generating":
                transition_project(
                    session,
                    project,
                    target="ready_for_generation",
                    actor_id="system:cad-recovery",
                    reason="A stale private CAD worker claim was terminally recovered.",
                    details={"candidate_id": candidate.id, "job_id": job.id},
                )
            session.add(
                AuditEvent(
                    project_id=project.id,
                    actor_id="system:cad-recovery",
                    event_type=event_type,
                    reason=event_reason,
                    details={"candidate_id": candidate.id, "job_id": job.id},
                )
            )
            await recovery_attempt.commit()
        dispatch_ids = list(
            (
                await session.scalars(
                    select(CadJob.candidate_id)
                    .join(CandidateDesign, CadJob.candidate_id == CandidateDesign.id)
                    .where(CadJob.status == "queued", CandidateDesign.status == "queued")
                    .order_by(CadJob.requested_at.asc())
                    .limit(CAD_RECOVERY_BATCH_LIMIT)
                )
            ).all()
        )
        await session.commit()
    dispatched = 0
    for candidate_id in dispatch_ids:
        try:
            compile_cad_candidate.delay(candidate_id)
            dispatched += 1
        except Exception:
            # Keep the durable queued record intact. The next sweep or an
            # idempotent API replay will safely attempt delivery again.
            continue
    return {"dispatched": dispatched, "stale_failed": stale_failed}


@celery_app.task(name="accessforge.jobs.process_deletion_jobs")  # type: ignore[untyped-decorator]
def process_deletion_jobs() -> int:
    return asyncio.run(_process_deletion_jobs())


@celery_app.task(name="accessforge.jobs.expire_pending_assets")  # type: ignore[untyped-decorator]
def expire_pending_assets() -> int:
    return asyncio.run(_expire_pending_assets())


@celery_app.task(name="accessforge.jobs.recover_cad_jobs")  # type: ignore[untyped-decorator]
def recover_cad_jobs() -> dict[str, int]:
    return asyncio.run(_recover_cad_jobs())


@celery_app.task(name="accessforge.jobs.compile_cad_candidate")  # type: ignore[untyped-decorator]
def compile_cad_candidate(candidate_id: str) -> str:
    """Run one durable, ID-only CAD job in the worker process."""

    return asyncio.run(_compile_cad_candidate(candidate_id))


async def _compile_cad_candidate(candidate_id: str) -> str:
    async with session_factory() as session:
        return await process_cad_candidate(session, candidate_id)


class PeriodicTaskSender(Protocol):
    def add_periodic_task(self, schedule: float, signature: object, *, name: str) -> object: ...


@celery_app.on_after_configure.connect  # type: ignore[untyped-decorator]
def setup_periodic_tasks(sender: PeriodicTaskSender, **_: object) -> None:
    """Run retention sweeps hourly when the worker is configured with beat."""
    signature: object = expire_pending_assets.s()
    sender.add_periodic_task(3600.0, signature, name="expire pending uploads")
    recovery_signature: object = recover_cad_jobs.s()
    sender.add_periodic_task(60.0, recovery_signature, name="recover durable CAD jobs")
