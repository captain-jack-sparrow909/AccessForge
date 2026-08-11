"""Retention, deletion, and durable private-job recovery tasks.

Deletion is a bounded outbox workflow.  Private object metadata is changed only
after an object-store delete succeeds, and a transient failure remains eligible
for a later, auditable retry.  The database is the source of truth; it never
stores raw storage-provider exception text as deletion status.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.cad.service import process_cad_candidate
from accessforge.db.models import (
    AuditEvent,
    CadJob,
    CandidateArtifact,
    CandidateDesign,
    DeletionJob,
    ExportBundle,
    MediaAsset,
    Project,
)
from accessforge.db.results import affected_row_count
from accessforge.db.session import session_factory
from accessforge.jobs.celery_app import celery_app
from accessforge.planning.service import reconcile_comparison_batch
from accessforge.projects.workflow import transition_project
from accessforge.storage.s3 import (
    PrivateObjectListing,
    delete_object,
    list_project_private_object_keys,
)

CAD_RECOVERY_BATCH_LIMIT = 100
CAD_RUNNING_STALE_AFTER = timedelta(minutes=20)
DELETION_RECOVERY_BATCH_LIMIT = 20
DELETION_MAX_ATTEMPTS = 5
DELETION_RETRY_BASE_DELAY = timedelta(minutes=1)
DELETION_RETRY_MAX_DELAY = timedelta(hours=1)
DELETION_RUNNING_STALE_AFTER = timedelta(minutes=20)
DELETION_OBJECT_DELETE_TIMEOUT_SECONDS = 60.0
DELETION_WRITE_SETTLE_DELAY = timedelta(minutes=2)
DELETION_RECONCILIATION_SETTLE_DELAY = timedelta(minutes=1)
DELETION_PREFIX_OBJECT_LIMIT = 1_000


class DeletionLeaseLost(Exception):
    """Raised when another recovery path has already reclaimed a deletion lease."""


class DeletionOperationTimedOut(TimeoutError):
    """An uncancellable SDK thread exceeded the worker's defensive timeout."""


class DeletionPrefixInventoryIncomplete(Exception):
    """The bounded project-prefix listing could not prove a complete inventory."""


class DeletionPrefixNotEmpty(Exception):
    """Private objects remained after a bounded project-prefix cleanup pass."""


def _deletion_retry_delay(attempt_count: int) -> timedelta:
    """Return a bounded exponential delay after a failed deletion attempt."""

    multiplier = 2 ** max(attempt_count - 1, 0)
    retry_delay = timedelta(
        seconds=DELETION_RETRY_BASE_DELAY.total_seconds() * multiplier,
    )
    if retry_delay > DELETION_RETRY_MAX_DELAY:
        return DELETION_RETRY_MAX_DELAY
    return retry_delay


def _deletion_error_code(exc: Exception) -> str:
    """Classify without retaining endpoint, object key, or provider error text."""

    if isinstance(exc, DeletionOperationTimedOut):
        return "object_storage_operation_timeout"
    if isinstance(exc, DeletionPrefixInventoryIncomplete):
        return "object_prefix_inventory_incomplete"
    if isinstance(exc, DeletionPrefixNotEmpty):
        return "object_prefix_not_empty"
    if isinstance(exc, (ConnectionError, OSError, TimeoutError)):
        return "object_storage_unavailable"
    return "object_storage_delete_failed"


async def _renew_deletion_lease(
    session: AsyncSession, *, job_id: str, lease_started_at: datetime
) -> datetime:
    """Publish a fresh lease before one bounded object-store operation."""

    renewed_at = datetime.now(UTC)
    result = await session.execute(
        update(DeletionJob)
        .where(
            DeletionJob.id == job_id,
            DeletionJob.status == "running",
            DeletionJob.started_at == lease_started_at,
        )
        .values(started_at=renewed_at)
    )
    if affected_row_count(result) != 1:
        await session.rollback()
        raise DeletionLeaseLost
    # Persist the heartbeat before a synchronous storage SDK operation runs in
    # a worker thread. The next claim must see the fresh lease, not a local
    # uncommitted timestamp.
    await session.commit()
    return renewed_at


async def _delete_private_object(object_key: str) -> None:
    """Bound one blocking SDK call so a worker does not hold a lease indefinitely."""

    try:
        await asyncio.wait_for(
            asyncio.to_thread(delete_object, object_key=object_key),
            timeout=DELETION_OBJECT_DELETE_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        # Cancelling wait_for does not stop a Python worker thread. Do not
        # automatically requeue this potentially still-in-flight deletion;
        # manual review avoids another worker overlapping the same object.
        raise DeletionOperationTimedOut from exc


async def _list_project_private_objects(project_id: str) -> PrivateObjectListing:
    """Bound one complete prefix inventory attempt at the storage boundary."""

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                list_project_private_object_keys,
                project_id=project_id,
                max_keys=DELETION_PREFIX_OBJECT_LIMIT,
            ),
            timeout=DELETION_OBJECT_DELETE_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise DeletionOperationTimedOut from exc


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def _defer_claimed_deletion_job(
    session: AsyncSession,
    *,
    job: DeletionJob,
    lease_started_at: datetime,
    now: datetime,
    next_attempt_at: datetime,
    error_code: str,
    reason: str,
    reconciliation_passes: int,
    last_reconciled_at: datetime | None,
) -> None:
    """Pause a lease for quiescence/reconciliation without consuming a retry."""

    result = await session.execute(
        update(DeletionJob)
        .where(
            DeletionJob.id == job.id,
            DeletionJob.status == "running",
            DeletionJob.started_at == lease_started_at,
        )
        .values(
            status="queued",
            attempt_count=max(job.attempt_count - 1, 0),
            started_at=None,
            next_attempt_at=next_attempt_at,
            last_error_code=error_code,
            last_error_at=now,
            reconciliation_passes=reconciliation_passes,
            last_reconciled_at=last_reconciled_at,
            completed_at=None,
            error=None,
        )
    )
    if affected_row_count(result) != 1:
        await session.rollback()
        raise DeletionLeaseLost
    session.add(
        AuditEvent(
            project_id=job.project_id,
            actor_id="system:deletion-worker",
            event_type="deletion.quiescence_deferred",
            reason=reason,
            details={
                "deletion_job_id": job.id,
                "error_code": error_code,
                "next_attempt_at": next_attempt_at.isoformat(),
                "reconciliation_passes": reconciliation_passes,
            },
        )
    )
    await session.commit()


async def _recover_stale_deletion_jobs(now: datetime | None = None) -> dict[str, int]:
    """Return expired deletion leases to the durable queue or bounded review state."""

    current_time = now or datetime.now(UTC)
    stale_before = current_time - DELETION_RUNNING_STALE_AFTER
    requeued = 0
    manual_review_required = 0
    async with session_factory() as session:
        jobs = list(
            (
                await session.scalars(
                    select(DeletionJob)
                    .where(
                        DeletionJob.status == "running",
                        DeletionJob.started_at.is_not(None),
                        DeletionJob.started_at < stale_before,
                    )
                    .order_by(DeletionJob.started_at.asc())
                    .limit(DELETION_RECOVERY_BATCH_LIMIT)
                )
            ).all()
        )
        for job in jobs:
            if job.started_at is None:
                continue
            terminal = job.attempt_count >= DELETION_MAX_ATTEMPTS
            result = await session.execute(
                update(DeletionJob)
                .where(
                    DeletionJob.id == job.id,
                    DeletionJob.status == "running",
                    DeletionJob.started_at == job.started_at,
                )
                .values(
                    status="manual_review_required" if terminal else "queued",
                    started_at=None,
                    next_attempt_at=None if terminal else current_time,
                    last_error_code="worker_lease_expired",
                    last_error_at=current_time,
                    reconciliation_passes=0,
                    last_reconciled_at=None,
                    completed_at=current_time if terminal else None,
                    error=None,
                )
            )
            if affected_row_count(result) != 1:
                continue
            if terminal:
                manual_review_required += 1
                session.add(
                    AuditEvent(
                        project_id=job.project_id,
                        actor_id="system:deletion-recovery",
                        event_type="deletion.manual_review_required",
                        reason=(
                            "A deletion worker lease repeatedly expired. Automatic cleanup stopped "
                            "without recording provider error text."
                        ),
                        details={
                            "deletion_job_id": job.id,
                            "attempt_count": job.attempt_count,
                            "error_code": "worker_lease_expired",
                        },
                    )
                )
            else:
                requeued += 1
                session.add(
                    AuditEvent(
                        project_id=job.project_id,
                        actor_id="system:deletion-recovery",
                        event_type="deletion.lease_reclaimed",
                        reason=(
                            "An expired deletion worker lease returned the durable cleanup job "
                            "to the bounded retry queue."
                        ),
                        details={
                            "deletion_job_id": job.id,
                            "attempt_count": job.attempt_count,
                            "error_code": "worker_lease_expired",
                        },
                    )
                )
        await session.commit()
    return {"requeued": requeued, "manual_review_required": manual_review_required}


async def _claim_deletion_job(job_id: str, now: datetime) -> datetime | None:
    """Atomically claim one due deletion job and return its lease timestamp."""

    async with session_factory() as session:
        result = await session.execute(
            update(DeletionJob)
            .where(
                DeletionJob.id == job_id,
                DeletionJob.status == "queued",
                or_(DeletionJob.next_attempt_at.is_(None), DeletionJob.next_attempt_at <= now),
            )
            .values(
                status="running",
                attempt_count=DeletionJob.attempt_count + 1,
                started_at=now,
                completed_at=None,
                error=None,
            )
        )
        if affected_row_count(result) != 1:
            await session.rollback()
            return None
        await session.commit()
    return now


async def _record_deletion_failure(
    *,
    job_id: str,
    lease_started_at: datetime,
    error_code: str,
    now: datetime,
    force_manual_review: bool = False,
) -> bool:
    """Record a CAS-guarded retry or terminal manual-review state without raw errors."""

    async with session_factory() as session:
        job = await session.scalar(
            select(DeletionJob).where(
                DeletionJob.id == job_id,
                DeletionJob.status == "running",
                DeletionJob.started_at == lease_started_at,
            )
        )
        if job is None:
            return False
        terminal = force_manual_review or job.attempt_count >= DELETION_MAX_ATTEMPTS
        next_attempt_at = None if terminal else now + _deletion_retry_delay(job.attempt_count)
        result = await session.execute(
            update(DeletionJob)
            .where(
                DeletionJob.id == job.id,
                DeletionJob.status == "running",
                DeletionJob.started_at == lease_started_at,
            )
            .values(
                status="manual_review_required" if terminal else "queued",
                started_at=None,
                next_attempt_at=next_attempt_at,
                last_error_code=error_code,
                last_error_at=now,
                reconciliation_passes=0,
                last_reconciled_at=None,
                completed_at=now if terminal else None,
                error=None,
            )
        )
        if affected_row_count(result) != 1:
            await session.rollback()
            return False
        session.add(
            AuditEvent(
                project_id=job.project_id,
                actor_id="system:deletion-worker",
                event_type=(
                    "deletion.manual_review_required" if terminal else "deletion.retry_scheduled"
                ),
                reason=(
                    (
                        "A deletion operation exceeded the worker timeout, so automatic retries "
                        "stopped to avoid overlapping private-object cleanup."
                        if error_code == "object_storage_operation_timeout"
                        else (
                            "The bounded project-prefix inventory was incomplete, so automatic "
                            "cleanup stopped without claiming success."
                            if error_code == "object_prefix_inventory_incomplete"
                            else "Automatic deletion cleanup reached its bounded retry limit."
                        )
                    )
                    if terminal
                    else "A private object cleanup attempt was deferred for a bounded retry."
                ),
                details={
                    "deletion_job_id": job.id,
                    "attempt_count": job.attempt_count,
                    "error_code": error_code,
                    **(
                        {}
                        if next_attempt_at is None
                        else {"next_attempt_at": next_attempt_at.isoformat()}
                    ),
                },
            )
        )
        await session.commit()
        return True


async def _process_claimed_deletion_job(job_id: str, lease_started_at: datetime) -> bool:
    """Delete one lease-owned project's private objects, then finalize its outbox row."""

    current_lease_started_at = lease_started_at
    try:
        async with session_factory() as session:
            job = await session.scalar(
                select(DeletionJob).where(
                    DeletionJob.id == job_id,
                    DeletionJob.status == "running",
                    DeletionJob.started_at == lease_started_at,
                )
            )
            if job is None:
                return False
            assets = list(
                (
                    await session.scalars(
                        select(MediaAsset).where(MediaAsset.project_id == job.project_id)
                    )
                ).all()
            )
            now = datetime.now(UTC)
            write_not_before = max(
                (_as_utc(asset.expires_at) + DELETION_WRITE_SETTLE_DELAY for asset in assets),
                default=None,
            )
            if write_not_before is not None and write_not_before > now:
                await _defer_claimed_deletion_job(
                    session,
                    job=job,
                    lease_started_at=current_lease_started_at,
                    now=now,
                    next_attempt_at=write_not_before,
                    error_code="awaiting_upload_write_quiescence",
                    reason=(
                        "Private cleanup paused until every issued direct-upload authorization "
                        "has expired and its settlement window has elapsed."
                    ),
                    reconciliation_passes=0,
                    last_reconciled_at=None,
                )
                return False
            active_cad_job_id = await session.scalar(
                select(CadJob.id)
                .where(
                    CadJob.project_id == job.project_id,
                    CadJob.status.in_({"queued", "running"}),
                )
                .limit(1)
            )
            if active_cad_job_id is not None:
                await _defer_claimed_deletion_job(
                    session,
                    job=job,
                    lease_started_at=current_lease_started_at,
                    now=now,
                    next_attempt_at=now + DELETION_RETRY_BASE_DELAY,
                    error_code="awaiting_server_write_quiescence",
                    reason=(
                        "Private cleanup paused while cooperative cancellation or recovery "
                        "finishes an active server-side CAD write window."
                    ),
                    reconciliation_passes=0,
                    last_reconciled_at=None,
                )
                return False
            candidate_artifacts = list(
                (
                    await session.scalars(
                        select(CandidateArtifact).where(
                            CandidateArtifact.project_id == job.project_id
                        )
                    )
                ).all()
            )
            export_bundles = list(
                (
                    await session.scalars(
                        select(ExportBundle).where(ExportBundle.project_id == job.project_id)
                    )
                ).all()
            )
            known_keys = list(
                dict.fromkeys(
                    [asset.object_key for asset in assets]
                    + [artifact.object_key for artifact in candidate_artifacts]
                    + [bundle.object_key for bundle in export_bundles]
                )
            )
            for object_key in known_keys:
                current_lease_started_at = await _renew_deletion_lease(
                    session,
                    job_id=job.id,
                    lease_started_at=current_lease_started_at,
                )
                await _delete_private_object(object_key)
            listing = await _list_project_private_objects(job.project_id)
            if not listing.complete:
                raise DeletionPrefixInventoryIncomplete
            for object_key in listing.keys:
                current_lease_started_at = await _renew_deletion_lease(
                    session,
                    job_id=job.id,
                    lease_started_at=current_lease_started_at,
                )
                await _delete_private_object(object_key)
            verification = await _list_project_private_objects(job.project_id)
            if not verification.complete:
                raise DeletionPrefixInventoryIncomplete
            if verification.keys:
                raise DeletionPrefixNotEmpty
            reconciled_at = datetime.now(UTC)
            objects_observed = bool(listing.keys)
            last_reconciled_at = (
                _as_utc(job.last_reconciled_at) if job.last_reconciled_at is not None else None
            )
            if objects_observed or job.reconciliation_passes < 1 or last_reconciled_at is None:
                await _defer_claimed_deletion_job(
                    session,
                    job=job,
                    lease_started_at=current_lease_started_at,
                    now=reconciled_at,
                    next_attempt_at=reconciled_at + DELETION_RECONCILIATION_SETTLE_DELAY,
                    error_code="awaiting_prefix_reconciliation",
                    reason=(
                        "The first complete project-prefix inventory was empty; a separated "
                        "confirmation pass is required before cleanup can complete."
                    ),
                    reconciliation_passes=1,
                    last_reconciled_at=reconciled_at,
                )
                return False
            confirmation_due_at = last_reconciled_at + DELETION_RECONCILIATION_SETTLE_DELAY
            if reconciled_at < confirmation_due_at:
                await _defer_claimed_deletion_job(
                    session,
                    job=job,
                    lease_started_at=current_lease_started_at,
                    now=reconciled_at,
                    next_attempt_at=confirmation_due_at,
                    error_code="awaiting_prefix_reconciliation",
                    reason=(
                        "The separated project-prefix confirmation pass is not due yet."
                    ),
                    reconciliation_passes=1,
                    last_reconciled_at=last_reconciled_at,
                )
                return False
            for asset in assets:
                asset.status = "deleted"
                asset.updated_at = reconciled_at
            for artifact in candidate_artifacts:
                await session.delete(artifact)
            for bundle in export_bundles:
                await session.delete(bundle)
            completed_at = reconciled_at
            result = await session.execute(
                update(DeletionJob)
                .where(
                    DeletionJob.id == job.id,
                    DeletionJob.status == "running",
                    DeletionJob.started_at == current_lease_started_at,
                )
                .values(
                    status="succeeded",
                    started_at=None,
                    next_attempt_at=None,
                    last_error_code=None,
                    last_error_at=None,
                    reconciliation_passes=2,
                    last_reconciled_at=completed_at,
                    completed_at=completed_at,
                    error=None,
                )
            )
            if affected_row_count(result) != 1:
                await session.rollback()
                return False
            session.add(
                AuditEvent(
                    project_id=job.project_id,
                    actor_id="system:deletion-worker",
                    event_type="deletion.succeeded",
                    reason=(
                        "Private object cleanup completed after separated empty project-prefix "
                        "inventories through the durable deletion outbox."
                    ),
                    details={"deletion_job_id": job.id, "attempt_count": job.attempt_count},
                )
            )
            await session.commit()
            return True
    except DeletionLeaseLost:
        # A stale worker may have completed an idempotent object-store delete,
        # but it must not overwrite the newer worker's database state.
        return False
    except DeletionOperationTimedOut as exc:
        await _record_deletion_failure(
            job_id=job_id,
            lease_started_at=current_lease_started_at,
            error_code=_deletion_error_code(exc),
            now=datetime.now(UTC),
            force_manual_review=True,
        )
        return False
    except DeletionPrefixInventoryIncomplete as exc:
        await _record_deletion_failure(
            job_id=job_id,
            lease_started_at=current_lease_started_at,
            error_code=_deletion_error_code(exc),
            now=datetime.now(UTC),
            force_manual_review=True,
        )
        return False
    except Exception as exc:  # pragma: no cover - branch exercised with synthetic storage failure
        await _record_deletion_failure(
            job_id=job_id,
            lease_started_at=current_lease_started_at,
            error_code=_deletion_error_code(exc),
            now=datetime.now(UTC),
        )
        return False


async def _process_deletion_jobs() -> int:
    """Recover and process a bounded batch of due deletion outbox rows."""

    now = datetime.now(UTC)
    await _recover_stale_deletion_jobs(now)
    async with session_factory() as session:
        job_ids = list(
            (
                await session.scalars(
                    select(DeletionJob.id)
                    .where(
                        DeletionJob.status == "queued",
                        or_(
                            DeletionJob.next_attempt_at.is_(None),
                            DeletionJob.next_attempt_at <= now,
                        ),
                    )
                    .order_by(DeletionJob.requested_at.asc())
                    .limit(DELETION_RECOVERY_BATCH_LIMIT)
                )
            ).all()
        )
    processed = 0
    for job_id in job_ids:
        lease_started_at = await _claim_deletion_job(job_id, datetime.now(UTC))
        if lease_started_at is not None and await _process_claimed_deletion_job(
            job_id, lease_started_at
        ):
            processed += 1
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
