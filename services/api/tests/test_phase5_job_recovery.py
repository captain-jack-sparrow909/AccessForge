"""Durable CAD outbox and stale-worker recovery behavior for Phase 5."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_cad_service import create_comparison_worker_fixture, create_worker_fixture

from accessforge.db.models import (
    AuditEvent,
    CadJob,
    CandidateDesign,
    CandidateGenerationBatch,
    DesignPlan,
    Project,
)
from accessforge.jobs import tasks as job_tasks


@pytest.mark.asyncio
async def test_recovery_retries_durable_queued_cad_job_after_broker_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed broker publish leaves the committed queue row available to the next sweep."""

    engine, factory, candidate_id, _ = await create_worker_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    try:

        def unavailable_dispatch(_: str) -> None:
            raise RuntimeError("synthetic broker outage")

        monkeypatch.setattr(
            job_tasks,
            "compile_cad_candidate",
            SimpleNamespace(delay=unavailable_dispatch),
        )
        assert await job_tasks._recover_cad_jobs() == {"dispatched": 0, "stale_failed": 0}

        async with factory() as session:
            candidate = await session.get(CandidateDesign, candidate_id)
            job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate_id))
            assert candidate is not None and candidate.status == "queued"
            assert job is not None and job.status == "queued"

        dispatched_ids: list[str] = []

        def record_dispatch(dispatched_candidate_id: str) -> None:
            dispatched_ids.append(dispatched_candidate_id)

        monkeypatch.setattr(
            job_tasks,
            "compile_cad_candidate",
            SimpleNamespace(delay=record_dispatch),
        )
        assert await job_tasks._recover_cad_jobs() == {"dispatched": 1, "stale_failed": 0}
        assert dispatched_ids == [candidate_id]

        async with factory() as session:
            candidate = await session.get(CandidateDesign, candidate_id)
            job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate_id))
            assert candidate is not None and candidate.status == "queued"
            assert job is not None and job.status == "queued"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_finishes_stale_cancel_requested_comparison_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancellation request wins over an expired worker lease and finishes its batch."""

    engine, factory, candidate_ids, plan_id, _ = await create_comparison_worker_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    now = datetime.now(UTC)
    stale_started_at = now - job_tasks.CAD_RUNNING_STALE_AFTER - timedelta(seconds=1)
    try:
        async with factory() as session:
            running_candidate = await session.get(CandidateDesign, candidate_ids[0])
            completed_candidate = await session.get(CandidateDesign, candidate_ids[1])
            running_job = await session.scalar(
                select(CadJob).where(CadJob.candidate_id == candidate_ids[0])
            )
            completed_job = await session.scalar(
                select(CadJob).where(CadJob.candidate_id == candidate_ids[1])
            )
            batch = await session.scalar(
                select(CandidateGenerationBatch).where(
                    CandidateGenerationBatch.design_plan_id == plan_id
                )
            )
            assert (
                running_candidate is not None
                and completed_candidate is not None
                and running_job is not None
                and completed_job is not None
                and batch is not None
            )
            running_candidate.status = "cancel_requested"
            running_candidate.started_at = stale_started_at
            running_job.status = "running"
            running_job.started_at = stale_started_at
            running_job.cancel_requested_at = now
            completed_candidate.status = "cancelled"
            completed_candidate.completed_at = now
            completed_job.status = "cancelled"
            completed_job.cancel_requested_at = now
            completed_job.cancelled_at = now
            completed_job.completed_at = now
            batch.status = "cancellation_requested"
            batch.cancel_requested_at = now
            await session.commit()

        monkeypatch.setattr(
            job_tasks,
            "compile_cad_candidate",
            SimpleNamespace(
                delay=lambda _: pytest.fail("cancelled child must not be redispatched")
            ),
        )
        recovery = await job_tasks._recover_cad_jobs()
        assert recovery["dispatched"] == 0
        assert recovery["stale_failed"] == 0

        async with factory() as session:
            candidate = await session.get(CandidateDesign, candidate_ids[0])
            job = await session.scalar(
                select(CadJob).where(CadJob.candidate_id == candidate_ids[0])
            )
            batch = await session.scalar(
                select(CandidateGenerationBatch).where(
                    CandidateGenerationBatch.design_plan_id == plan_id
                )
            )
            plan = await session.get(DesignPlan, plan_id)
            project = await session.get(Project, "00000000-0000-0000-0000-000000000001")
            assert candidate is not None and candidate.status == "cancelled"
            assert job is not None and job.status == "cancelled"
            assert batch is not None and batch.status == "cancelled"
            assert plan is not None and plan.status == "comparison_cancelled"
            assert project is not None and project.status == "ready_for_generation"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_terminally_fails_stale_running_cad_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An expired worker lease never retries an uncertain private compilation."""

    engine, factory, candidate_id, _ = await create_worker_fixture(tmp_path)
    monkeypatch.setattr(job_tasks, "session_factory", factory)
    stale_started_at = datetime.now(UTC) - job_tasks.CAD_RUNNING_STALE_AFTER - timedelta(seconds=1)
    try:
        async with factory() as session:
            candidate = await session.get(CandidateDesign, candidate_id)
            job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate_id))
            assert candidate is not None and job is not None
            candidate.status = "running"
            candidate.started_at = stale_started_at
            job.status = "running"
            job.started_at = stale_started_at
            await session.commit()

        monkeypatch.setattr(
            job_tasks,
            "compile_cad_candidate",
            SimpleNamespace(delay=lambda _: pytest.fail("stale job must not be redispatched")),
        )
        assert await job_tasks._recover_cad_jobs() == {"dispatched": 0, "stale_failed": 1}

        async with factory() as session:
            candidate = await session.get(CandidateDesign, candidate_id)
            job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate_id))
            project = await session.get(Project, "00000000-0000-0000-0000-000000000001")
            assert project is not None
            audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.project_id == project.id,
                    AuditEvent.event_type == "candidate.worker_lease_expired",
                )
            )
            assert candidate is not None and candidate.status == "failed"
            assert candidate.failure_category == "worker_lease_expired"
            assert job is not None and job.status == "failed"
            assert job.failure_category == "worker_lease_expired"
            assert project.status == "ready_for_generation"
            assert audit is not None
    finally:
        await engine.dispose()
