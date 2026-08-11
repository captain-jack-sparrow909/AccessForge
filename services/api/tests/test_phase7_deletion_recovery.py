"""Synthetic regression coverage for Phase 7 deletion-outbox recovery.

These tests use temporary SQLite metadata and in-process storage doubles only.
They do not contact object storage, a broker, a deployment, or real project data.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from test_phase4_design_api import api_headers

from accessforge.api.routes.projects import delete_project, get_session
from accessforge.core.config import Settings
from accessforge.core.security import Principal
from accessforge.db.models import (
    AuditEvent,
    Base,
    CadJob,
    CandidateDesign,
    DeletionJob,
    MediaAsset,
    Project,
    User,
)
from accessforge.jobs import tasks as job_tasks
from accessforge.main import app
from accessforge.storage import s3 as storage_s3


@pytest.fixture(autouse=True)
def empty_project_prefix_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    def empty_listing(*, project_id: str, max_keys: int) -> storage_s3.PrivateObjectListing:
        assert project_id
        assert max_keys > 0
        return storage_s3.PrivateObjectListing(keys=(), complete=True)

    monkeypatch.setattr(job_tasks, "list_project_private_object_keys", empty_listing)


async def create_deletion_fixture(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession], str, str]:
    database_path = tmp_path / "phase7-deletion.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    project_id = "00000000-0000-0000-0000-000000000701"
    job_id = "00000000-0000-0000-0000-000000000702"
    async with factory() as session:
        session.add(User(id="phase7-deletion-owner", email="owner@example.test"))
        session.add(
            Project(
                id=project_id,
                owner_id="phase7-deletion-owner",
                name="Synthetic deletion recovery fixture",
                scope_status="supported",
                scope_reason="Synthetic test only.",
                status="deleted",
            )
        )
        session.add(
            MediaAsset(
                id="00000000-0000-0000-0000-000000000703",
                project_id=project_id,
                object_key="synthetic/phase7/private-input.png",
                media_type="still_image",
                content_type="image/png",
                original_name="synthetic-input.png",
                expected_size=64,
                actual_size=64,
                checksum_sha256="a" * 64,
                status="complete",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        session.add(
            DeletionJob(
                id=job_id,
                project_id=project_id,
                requested_by="phase7-deletion-owner",
            )
        )
        await session.commit()
    return engine, factory, project_id, job_id


@pytest.mark.asyncio
async def test_deletion_storage_failure_is_sanitized_and_due_retry_can_succeed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, project_id, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    private_marker = "https://storage.example.test/private/secret-object"
    try:

        def unavailable_storage(*, object_key: str) -> None:
            assert object_key.startswith("synthetic/phase7/")
            raise OSError(private_marker)

        monkeypatch.setattr(job_tasks, "delete_object", unavailable_storage)
        assert await job_tasks._process_deletion_jobs() == 0

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            asset = await session.scalar(
                select(MediaAsset).where(MediaAsset.project_id == project_id)
            )
            retry_audit = await session.scalar(
                select(AuditEvent).where(AuditEvent.event_type == "deletion.retry_scheduled")
            )
            assert job is not None and asset is not None and retry_audit is not None
            assert job.status == "queued"
            assert job.attempt_count == 1
            assert job.last_error_code == "object_storage_unavailable"
            assert job.last_error_at is not None
            assert job.next_attempt_at is not None
            assert job.error is None
            assert asset.status == "complete"
            assert private_marker not in json.dumps(retry_audit.details)
            job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

        deleted_keys: list[str] = []

        def available_storage(*, object_key: str) -> None:
            deleted_keys.append(object_key)

        monkeypatch.setattr(job_tasks, "delete_object", available_storage)
        assert await job_tasks._process_deletion_jobs() == 0

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            assert job is not None
            assert job.status == "queued"
            assert job.reconciliation_passes == 1
            assert job.last_reconciled_at is not None
            job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            job.last_reconciled_at = datetime.now(UTC) - (
                job_tasks.DELETION_RECONCILIATION_SETTLE_DELAY + timedelta(seconds=1)
            )
            await session.commit()

        assert await job_tasks._process_deletion_jobs() == 1

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            asset = await session.scalar(
                select(MediaAsset).where(MediaAsset.project_id == project_id)
            )
            assert job is not None and asset is not None
            assert job.status == "succeeded"
            assert job.completed_at is not None
            assert job.last_error_code is None
            assert asset.status == "deleted"
            assert deleted_keys == [
                "synthetic/phase7/private-input.png",
                "synthetic/phase7/private-input.png",
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_presigned_write_window_defers_without_consuming_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, project_id, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    deleted_keys: list[str] = []
    try:
        async with factory() as session:
            asset = await session.scalar(
                select(MediaAsset).where(MediaAsset.project_id == project_id)
            )
            assert asset is not None
            asset.expires_at = datetime.now(UTC) + timedelta(minutes=5)
            write_not_before = asset.expires_at + job_tasks.DELETION_WRITE_SETTLE_DELAY
            await session.commit()

        monkeypatch.setattr(
            job_tasks,
            "delete_object",
            lambda *, object_key: deleted_keys.append(object_key),
        )
        assert await job_tasks._process_deletion_jobs() == 0

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            asset = await session.scalar(
                select(MediaAsset).where(MediaAsset.project_id == project_id)
            )
            assert job is not None and asset is not None
            assert job.status == "queued"
            assert job.attempt_count == 0
            assert job.reconciliation_passes == 0
            assert job.last_error_code == "awaiting_upload_write_quiescence"
            assert job.next_attempt_at is not None
            assert job_tasks._as_utc(job.next_attempt_at) >= job_tasks._as_utc(write_not_before)
            assert asset.status == "complete"
            assert deleted_keys == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_late_prefix_object_resets_the_separated_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, _, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    deleted_keys: list[str] = []
    listings = iter(
        (
            storage_s3.PrivateObjectListing(keys=("private/project/orphan",), complete=True),
            storage_s3.PrivateObjectListing(keys=(), complete=True),
            storage_s3.PrivateObjectListing(keys=("private/project/late",), complete=True),
            storage_s3.PrivateObjectListing(keys=(), complete=True),
            storage_s3.PrivateObjectListing(keys=(), complete=True),
            storage_s3.PrivateObjectListing(keys=(), complete=True),
        )
    )

    def next_listing(*, project_id: str, max_keys: int) -> storage_s3.PrivateObjectListing:
        del project_id, max_keys
        return next(listings)

    monkeypatch.setattr(job_tasks, "list_project_private_object_keys", next_listing)
    monkeypatch.setattr(
        job_tasks,
        "delete_object",
        lambda *, object_key: deleted_keys.append(object_key),
    )
    try:
        assert await job_tasks._process_deletion_jobs() == 0
        await _make_reconciliation_due(factory, job_id)

        assert await job_tasks._process_deletion_jobs() == 0
        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            assert job is not None
            assert job.status == "queued"
            assert job.reconciliation_passes == 1
            assert job.last_reconciled_at is not None
            second_pass_time = job_tasks._as_utc(job.last_reconciled_at)

        await _make_reconciliation_due(factory, job_id)
        assert await job_tasks._process_deletion_jobs() == 1

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            assert job is not None
            assert job.status == "succeeded"
            assert job.reconciliation_passes == 2
            assert job.last_reconciled_at is not None
            assert job_tasks._as_utc(job.last_reconciled_at) > second_pass_time
        assert "private/project/orphan" in deleted_keys
        assert "private/project/late" in deleted_keys
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_incomplete_prefix_inventory_never_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, _, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    monkeypatch.setattr(
        job_tasks,
        "list_project_private_object_keys",
        lambda *, project_id, max_keys: storage_s3.PrivateObjectListing(
            keys=(f"private/{project_id}/bounded",), complete=False
        ),
    )
    monkeypatch.setattr(job_tasks, "delete_object", lambda *, object_key: None)
    try:
        assert await job_tasks._process_deletion_jobs() == 0
        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            assert job is not None
            assert job.status == "manual_review_required"
            assert job.last_error_code == "object_prefix_inventory_incomplete"
            assert job.reconciliation_passes == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_active_cad_write_window_defers_private_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, project_id, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    deleted_keys: list[str] = []
    candidate_id = "00000000-0000-0000-0000-000000000706"
    try:
        async with factory() as session:
            session.add(
                _candidate(candidate_id=candidate_id, project_id=project_id, status="running")
            )
            session.add(
                CadJob(
                    id="00000000-0000-0000-0000-000000000707",
                    project_id=project_id,
                    candidate_id=candidate_id,
                    idempotency_key="phase7-active-write",
                    status="running",
                    input_hash="b" * 64,
                    requested_by="phase7-deletion-owner",
                )
            )
            await session.commit()

        monkeypatch.setattr(
            job_tasks,
            "delete_object",
            lambda *, object_key: deleted_keys.append(object_key),
        )
        assert await job_tasks._process_deletion_jobs() == 0

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            assert job is not None
            assert job.status == "queued"
            assert job.attempt_count == 0
            assert job.last_error_code == "awaiting_server_write_quiescence"
            assert job.reconciliation_passes == 0
            assert deleted_keys == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_deletion_lease_returns_to_the_durable_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, project_id, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    try:
        stale_started_at = (
            datetime.now(UTC) - job_tasks.DELETION_RUNNING_STALE_AFTER - timedelta(seconds=1)
        )
        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            assert job is not None
            job.status = "running"
            job.attempt_count = 1
            job.started_at = stale_started_at
            await session.commit()

        recovery = await job_tasks._recover_stale_deletion_jobs()
        assert recovery == {"requeued": 1, "manual_review_required": 0}

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.project_id == project_id,
                    AuditEvent.event_type == "deletion.lease_reclaimed",
                )
            )
            assert job is not None and audit is not None
            assert job.status == "queued"
            assert job.started_at is None
            assert job.next_attempt_at is not None
            assert job.last_error_code == "worker_lease_expired"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_deletion_retry_limit_requires_manual_review_without_raw_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, project_id, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    private_marker = "bucket=private&token=should-not-persist"
    try:
        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            assert job is not None
            job.attempt_count = job_tasks.DELETION_MAX_ATTEMPTS - 1
            await session.commit()

        def terminal_failure(*, object_key: str) -> None:
            raise RuntimeError(private_marker)

        monkeypatch.setattr(job_tasks, "delete_object", terminal_failure)
        assert await job_tasks._process_deletion_jobs() == 0

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.project_id == project_id,
                    AuditEvent.event_type == "deletion.manual_review_required",
                )
            )
            assert job is not None and audit is not None
            assert job.status == "manual_review_required"
            assert job.attempt_count == job_tasks.DELETION_MAX_ATTEMPTS
            assert job.next_attempt_at is None
            assert job.completed_at is not None
            assert job.last_error_code == "object_storage_delete_failed"
            assert job.error is None
            assert private_marker not in json.dumps(audit.details)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_deletion_timeout_requires_manual_review_to_avoid_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory, _, job_id = await create_deletion_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    try:

        async def timed_out_object_delete(object_key: str) -> None:
            del object_key
            raise job_tasks.DeletionOperationTimedOut

        monkeypatch.setattr(job_tasks, "_delete_private_object", timed_out_object_delete)
        assert await job_tasks._process_deletion_jobs() == 0

        async with factory() as session:
            job = await session.get(DeletionJob, job_id)
            audit = await session.scalar(
                select(AuditEvent).where(AuditEvent.event_type == "deletion.manual_review_required")
            )
            assert job is not None and audit is not None
            assert job.status == "manual_review_required"
            assert job.next_attempt_at is None
            assert job.last_error_code == "object_storage_operation_timeout"
            assert "overlapping" in audit.reason
    finally:
        await engine.dispose()


def test_storage_client_uses_one_bounded_sdk_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_client(service_name: str, **kwargs: object) -> object:
        received["service_name"] = service_name
        received.update(kwargs)
        return object()

    monkeypatch.setattr(storage_s3.boto3, "client", fake_client)
    storage_s3.storage_client()

    request_config = received["config"]
    assert isinstance(request_config, storage_s3.Config)
    assert request_config.connect_timeout + request_config.read_timeout < (
        job_tasks.DELETION_OBJECT_DELETE_TIMEOUT_SECONDS
    )
    assert request_config.retries == {"mode": "standard", "total_max_attempts": 1}


def test_storage_timeout_override_cannot_exceed_deletion_worker_budget() -> None:
    with pytest.raises(ValueError, match="must total less than 60 seconds"):
        Settings(s3_connect_timeout_seconds=20, s3_read_timeout_seconds=40)


def test_project_prefix_inventory_is_paginated_and_fixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class ListingClient:
        def list_objects_v2(self, **kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            if len(calls) == 1:
                return {
                    "Contents": [{"Key": "private/project-1/first"}],
                    "IsTruncated": True,
                    "NextContinuationToken": "next-page",
                }
            return {
                "Contents": [
                    {"Key": "private/project-1/second"},
                    {"Key": "private/another-project/not-in-scope"},
                ],
                "IsTruncated": False,
            }

    monkeypatch.setattr(storage_s3, "storage_client", lambda: ListingClient())
    listing = storage_s3.list_project_private_object_keys(project_id="project-1", max_keys=10)

    assert listing == storage_s3.PrivateObjectListing(
        keys=("private/project-1/first", "private/project-1/second"),
        complete=True,
    )
    assert calls[0]["Prefix"] == "private/project-1/"
    assert calls[1]["ContinuationToken"] == "next-page"


@pytest.mark.asyncio
async def test_only_one_active_deletion_outbox_can_exist_per_project(
    tmp_path: Path,
) -> None:
    engine, factory, project_id, _ = await create_deletion_fixture(tmp_path)
    try:
        async with factory() as session:
            session.add(
                DeletionJob(
                    id="00000000-0000-0000-0000-000000000704",
                    project_id=project_id,
                    requested_by="phase7-deletion-owner",
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_initial_deletes_return_the_same_durable_result() -> None:
    database_url = os.environ.get("ACCESSFORGE_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip(
            "Set ACCESSFORGE_TEST_POSTGRES_URL to a migrated disposable PostgreSQL database "
            "to exercise real row-lock concurrency."
        )
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    project_id = str(uuid4())
    principal = Principal(
        subject=f"phase7-concurrent-owner-{uuid4()}",
        email=f"phase7-concurrent-{uuid4()}@example.test",
        role="member",
    )
    try:
        async with factory() as session:
            session.add(User(id=principal.subject, email=principal.email))
            session.add(
                Project(
                    id=project_id,
                    owner_id=principal.subject,
                    name="Synthetic concurrent deletion fixture",
                    scope_status="supported",
                    scope_reason="Synthetic test only.",
                )
            )
            await session.commit()

        async def delete_once() -> dict[str, str]:
            async with factory() as session:
                return await delete_project(project_id, principal=principal, session=session)

        results = await asyncio.wait_for(asyncio.gather(delete_once(), delete_once()), timeout=10)
        assert results == [
            {"project_id": project_id, "status": "deletion_queued"},
            {"project_id": project_id, "status": "deletion_queued"},
        ]
        assert await _deletion_job_count(factory, project_id) == 1
    finally:
        async with factory() as session:
            await session.execute(sql_delete(User).where(User.id == principal.subject))
            await session.commit()
        await engine.dispose()


def test_owner_can_read_sanitized_deletion_status_after_soft_delete(tmp_path: Path) -> None:
    owner_headers = api_headers(f"phase7-deletion-owner-{uuid4()}")
    other_headers = api_headers(f"phase7-deletion-other-{uuid4()}")
    database_path = tmp_path / "phase7-deletion-status.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        asyncio.run(_create_all(engine))
        with TestClient(app) as client:
            create_response = client.post(
                "/v1/projects",
                headers=owner_headers,
                json={
                    "name": f"Phase 7 deletion status fixture {uuid4()}",
                    "object_description": "A synthetic zipper tab.",
                    "action_description": "A gentle synthetic pull.",
                    "environment": "Synthetic indoor test only.",
                    "load_context": "low",
                    "safety_system": False,
                    "age_context": "adult",
                },
            )
            assert create_response.status_code == 201, create_response.text
            project_id = create_response.json()["id"]

            delete_response = client.delete(f"/v1/projects/{project_id}", headers=owner_headers)
            assert delete_response.status_code == 202, delete_response.text
            repeat_delete_response = client.delete(
                f"/v1/projects/{project_id}", headers=owner_headers
            )
            assert repeat_delete_response.status_code == 202, repeat_delete_response.text
            assert (
                client.get(f"/v1/projects/{project_id}", headers=owner_headers).status_code == 404
            )

            status_response = client.get(
                f"/v1/projects/{project_id}/deletion-status", headers=owner_headers
            )
            assert status_response.status_code == 200, status_response.text
            payload = status_response.json()
            assert payload["status"] == "queued"
            assert payload["attempt_count"] == 0
            assert payload["reconciliation_passes"] == 0
            assert payload["last_reconciled_at"] is None
            assert "error" not in payload
            assert "requested_by" not in payload
            assert (
                client.get(
                    f"/v1/projects/{project_id}/deletion-status", headers=other_headers
                ).status_code
                == 404
            )
        assert asyncio.run(_deletion_job_count(factory, project_id)) == 1
    finally:
        app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())


@pytest.mark.asyncio
async def test_delete_fences_queued_and_running_cad_work(tmp_path: Path) -> None:
    database_path = tmp_path / "phase7-write-fence.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    project_id = "00000000-0000-0000-0000-000000000708"
    queued_candidate_id = "00000000-0000-0000-0000-000000000709"
    running_candidate_id = "00000000-0000-0000-0000-000000000710"
    principal = Principal(subject="phase7-write-fence-owner", email=None, role="member")
    try:
        await _create_all(engine)
        async with factory() as session:
            session.add(User(id=principal.subject, email=None))
            session.add(
                Project(
                    id=project_id,
                    owner_id=principal.subject,
                    name="Synthetic private-write fence",
                    scope_status="supported",
                    scope_reason="Synthetic test only.",
                    status="generating",
                )
            )
            session.add(
                _candidate(
                    candidate_id=queued_candidate_id,
                    project_id=project_id,
                    status="queued",
                )
            )
            session.add(
                _candidate(
                    candidate_id=running_candidate_id,
                    project_id=project_id,
                    status="running",
                )
            )
            session.add_all(
                [
                    CadJob(
                        project_id=project_id,
                        candidate_id=queued_candidate_id,
                        idempotency_key="phase7-queued-write",
                        status="queued",
                        input_hash="e" * 64,
                        requested_by=principal.subject,
                    ),
                    CadJob(
                        project_id=project_id,
                        candidate_id=running_candidate_id,
                        idempotency_key="phase7-running-write",
                        status="running",
                        input_hash="f" * 64,
                        requested_by=principal.subject,
                    ),
                ]
            )
            await session.commit()

        async with factory() as session:
            result = await delete_project(project_id, principal=principal, session=session)
            assert result == {"project_id": project_id, "status": "deletion_queued"}

        async with factory() as session:
            project = await session.get(Project, project_id)
            queued_candidate = await session.get(CandidateDesign, queued_candidate_id)
            running_candidate = await session.get(CandidateDesign, running_candidate_id)
            jobs = {
                job.candidate_id: job
                for job in (
                    await session.scalars(select(CadJob).where(CadJob.project_id == project_id))
                ).all()
            }
            audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.project_id == project_id,
                    AuditEvent.event_type == "deletion.private_writes_fenced",
                )
            )
            assert project is not None and project.status == "deleted"
            assert queued_candidate is not None and queued_candidate.status == "cancelled"
            assert running_candidate is not None and running_candidate.status == "cancel_requested"
            assert jobs[queued_candidate_id].status == "cancelled"
            assert jobs[queued_candidate_id].cancelled_at is not None
            assert jobs[running_candidate_id].status == "running"
            assert jobs[running_candidate_id].cancel_requested_at is not None
            assert audit is not None
    finally:
        await engine.dispose()


async def _create_all(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _deletion_job_count(factory: async_sessionmaker[AsyncSession], project_id: str) -> int:
    async with factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(DeletionJob)
                .where(DeletionJob.project_id == project_id)
            )
            or 0
        )


async def _make_reconciliation_due(factory: async_sessionmaker[AsyncSession], job_id: str) -> None:
    async with factory() as session:
        job = await session.get(DeletionJob, job_id)
        assert job is not None
        job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        job.last_reconciled_at = datetime.now(UTC) - (
            job_tasks.DELETION_RECONCILIATION_SETTLE_DELAY + timedelta(seconds=1)
        )
        await session.commit()


def _candidate(*, candidate_id: str, project_id: str, status: str) -> CandidateDesign:
    return CandidateDesign(
        id=candidate_id,
        project_id=project_id,
        design_spec_id="00000000-0000-0000-0000-000000000799",
        candidate_number=1,
        status=status,
        template_id="synthetic-phase7",
        template_version="1",
        template_manifest_sha256="c" * 64,
        spec_hash="d" * 64,
        generation_seed="phase7-seed",
    )


def test_declarative_schedule_contains_durable_recovery_tasks() -> None:
    from accessforge.jobs.celery_app import CELERY_BEAT_SCHEDULE

    assert CELERY_BEAT_SCHEDULE["process durable deletion outbox"] == {
        "task": "accessforge.jobs.process_deletion_jobs",
        "schedule": 60.0,
    }
    assert CELERY_BEAT_SCHEDULE["recover durable CAD jobs"] == {
        "task": "accessforge.jobs.recover_cad_jobs",
        "schedule": 60.0,
    }
    assert CELERY_BEAT_SCHEDULE["expire pending uploads"] == {
        "task": "accessforge.jobs.expire_pending_assets",
        "schedule": 3600.0,
    }


def test_clean_celery_process_discovers_durable_task_module() -> None:
    script = """
from accessforge.jobs.celery_app import celery_app
celery_app.loader.import_default_modules()
celery_app.finalize(auto=True)
required = {
    'accessforge.jobs.compile_cad_candidate',
    'accessforge.jobs.process_deletion_jobs',
    'accessforge.jobs.recover_cad_jobs',
}
missing = required.difference(celery_app.tasks)
expected_schedule = {
    'expire pending uploads': ('accessforge.jobs.expire_pending_assets', 3600.0),
    'process durable deletion outbox': ('accessforge.jobs.process_deletion_jobs', 60.0),
    'recover durable CAD jobs': ('accessforge.jobs.recover_cad_jobs', 60.0),
}
schedule_errors = {
    name: entry
    for name, (task, interval) in expected_schedule.items()
    if (entry := celery_app.conf.beat_schedule.get(name)) is None
    or entry.get('task') != task
    or entry.get('schedule') != interval
}
if missing:
    raise SystemExit(f'missing task registrations: {sorted(missing)}')
if schedule_errors:
    raise SystemExit(f'invalid beat schedule entries: {schedule_errors}')
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        cwd=Path(__file__).parents[1],
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_render_has_one_migration_owner_and_read_only_worker_schema_gates() -> None:
    blueprint = (Path(__file__).parents[3] / "render.yaml").read_text(encoding="utf-8")
    assert blueprint.count("preDeployCommand: alembic upgrade head") == 1
    assert blueprint.count("python -m accessforge.db.schema_gate && celery") == 2
