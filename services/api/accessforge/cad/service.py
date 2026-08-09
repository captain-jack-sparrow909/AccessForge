"""Durable candidate processing around the isolated deterministic compiler."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.cad.compiler import CadCompilationError, CompilationResult
from accessforge.cad.sandbox import CadIsolationError, run_isolated_compilation
from accessforge.cad.schemas import DesignSpec, canonical_hash
from accessforge.db.models import (
    AuditEvent,
    CadJob,
    CandidateArtifact,
    CandidateDesign,
    CandidateGenerationBatch,
    CandidateValidationRun,
    DesignSpecRevision,
    Project,
)
from accessforge.db.results import affected_row_count
from accessforge.planning.service import mark_comparison_batch_running, reconcile_comparison_batch
from accessforge.projects.workflow import transition_project
from accessforge.risk.service import RiskGateError, assert_generation_allowed
from accessforge.storage.s3 import delete_object, put_private_bytes
from accessforge.validation.service import (
    VALIDATOR_HASH,
    VALIDATOR_VERSION,
    normalize_validation_report,
)


def artifact_object_key(
    *, project_id: str, candidate_id: str, checksum_sha256: str, filename: str
) -> str:
    """Generate a fixed private namespace with no user-controlled path fragments."""

    return f"private/{project_id}/candidates/{candidate_id}/{checksum_sha256}/{filename}"


def short_failure_detail(error: Exception) -> str:
    """Keep native CAD errors out of durable user/project records."""

    return str(error).replace("\n", " ")[:500] or "The isolated CAD compiler did not complete."


async def _candidate_and_job(
    session: AsyncSession, candidate_id: str
) -> tuple[CandidateDesign, CadJob, DesignSpecRevision, Project] | None:
    candidate = await session.scalar(
        select(CandidateDesign).where(CandidateDesign.id == candidate_id)
    )
    if candidate is None:
        return None
    job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate.id))
    spec_revision = await session.scalar(
        select(DesignSpecRevision).where(DesignSpecRevision.id == candidate.design_spec_id)
    )
    project = await session.scalar(select(Project).where(Project.id == candidate.project_id))
    if job is None or spec_revision is None or project is None:
        raise CadCompilationError(
            "The durable candidate job is missing required immutable records."
        )
    return candidate, job, spec_revision, project


async def _mark_failed(
    session: AsyncSession,
    *,
    candidate: CandidateDesign,
    job: CadJob,
    project: Project,
    category: str,
    error: Exception,
) -> None:
    # Do not let an error path overwrite a cancellation or a terminal outcome
    # committed by a competing at-least-once delivery.
    await session.refresh(candidate)
    await session.refresh(job)
    if candidate.status in {"succeeded", "failed", "cancelled"}:
        return
    if candidate.status == "cancel_requested" or job.cancel_requested_at is not None:
        await mark_candidate_cancelled(
            session,
            candidate=candidate,
            job=job,
            project=project,
            actor_id="system:cad-worker",
            reason="A cancellation request won the CAD worker error race.",
        )
        return
    now = datetime.now(UTC)
    detail = short_failure_detail(error)
    candidate.status = "failed"
    candidate.failure_category = category
    candidate.failure_detail = detail
    candidate.completed_at = now
    job.status = "failed"
    job.failure_category = category
    job.failure_detail = detail
    job.completed_at = now
    if candidate.generation_batch_id is not None:
        await reconcile_comparison_batch(
            session,
            project=project,
            batch_id=candidate.generation_batch_id,
            actor_id="system:cad-worker",
        )
    elif project.status == "generating":
        transition_project(
            session,
            project,
            target="ready_for_generation",
            actor_id="system:cad-worker",
            reason="A deterministic CAD job failed before it produced an immutable candidate.",
            details={"candidate_id": candidate.id, "failure_category": category},
        )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id="system:cad-worker",
            event_type="candidate.failed",
            reason="The isolated CAD compiler did not produce a complete artifact bundle.",
            details={"candidate_id": candidate.id, "job_id": job.id, "failure_category": category},
        )
    )
    await session.commit()


async def mark_candidate_cancelled(
    session: AsyncSession,
    *,
    candidate: CandidateDesign,
    job: CadJob,
    project: Project,
    actor_id: str,
    reason: str,
) -> None:
    """Finish a queued or cooperative in-flight cancellation without calling it a failure."""

    now = datetime.now(UTC)
    candidate.status = "cancelled"
    candidate.completed_at = now
    job.status = "cancelled"
    job.cancel_requested_at = job.cancel_requested_at or now
    job.cancelled_at = now
    job.completed_at = now
    if candidate.generation_batch_id is not None:
        await reconcile_comparison_batch(
            session,
            project=project,
            batch_id=candidate.generation_batch_id,
            actor_id=actor_id,
        )
    elif project.status == "generating":
        transition_project(
            session,
            project,
            target="ready_for_generation",
            actor_id=actor_id,
            reason=(
                "A private CAD candidate was cancelled before a complete artifact bundle persisted."
            ),
            details={"candidate_id": candidate.id, "job_id": job.id},
        )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="candidate.cancelled",
            reason=reason,
            details={"candidate_id": candidate.id, "job_id": job.id},
        )
    )
    await session.commit()


def _validation_has_failure(report: dict[str, object]) -> bool:
    findings = report.get("findings")
    if not isinstance(findings, list):
        return True
    return any(
        isinstance(finding, dict) and finding.get("status") in {"failed", "error"}
        for finding in findings
    )


async def process_cad_candidate(session: AsyncSession, candidate_id: str) -> str:
    """Process one queued candidate.  This function is intentionally not a retry loop."""

    loaded = await _candidate_and_job(session, candidate_id)
    if loaded is None:
        return "missing"
    candidate, job, spec_revision, project = loaded
    if candidate.status == "cancel_requested" or job.cancel_requested_at is not None:
        await mark_candidate_cancelled(
            session,
            candidate=candidate,
            job=job,
            project=project,
            actor_id="system:cad-worker",
            reason="A cancellation request was observed before compilation began.",
        )
        return "cancelled"
    if candidate.status != "queued" or job.status != "queued":
        return "already_processed"
    if project.status != "generating":
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="invalid_project_state",
            error=CadCompilationError("Project is not in the generating state."),
        )
        return "failed"
    authorized_plan_id: str | None = None
    if candidate.risk_assessment_id is None:
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="risk_gate_changed",
            error=CadCompilationError("Candidate is missing immutable risk-assessment lineage."),
        )
        return "failed"
    if candidate.generation_batch_id is not None:
        batch = await session.scalar(
            select(CandidateGenerationBatch)
            .where(CandidateGenerationBatch.id == candidate.generation_batch_id)
            .execution_options(populate_existing=True)
        )
        if (
            batch is None
            or batch.project_id != project.id
            or batch.risk_assessment_id != candidate.risk_assessment_id
        ):
            await _mark_failed(
                session,
                candidate=candidate,
                job=job,
                project=project,
                category="risk_gate_changed",
                error=CadCompilationError("The candidate comparison lineage is incomplete."),
            )
            return "failed"
        authorized_plan_id = batch.design_plan_id
    try:
        await assert_generation_allowed(
            session,
            project=project,
            design_spec=spec_revision,
            expected_assessment_id=candidate.risk_assessment_id,
            authorized_plan_id=authorized_plan_id,
        )
    except RiskGateError as exc:
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="risk_gate_changed",
            error=CadCompilationError(str(exc)),
        )
        return "failed"
    started_at = datetime.now(UTC)
    # Celery delivery is at-least-once. Claim both durable rows with
    # compare-and-set updates before compiling so a duplicate message cannot
    # create a second artifact set for the same immutable candidate.
    candidate_claim = await session.execute(
        update(CandidateDesign)
        .where(CandidateDesign.id == candidate.id, CandidateDesign.status == "queued")
        .values(
            status="running",
            started_at=started_at,
            failure_category=None,
            failure_detail=None,
        )
    )
    if affected_row_count(candidate_claim) != 1:
        await session.rollback()
        return "already_processed"
    job_claim = await session.execute(
        update(CadJob)
        .where(
            CadJob.id == job.id,
            CadJob.status == "queued",
            CadJob.cancel_requested_at.is_(None),
        )
        .values(
            status="running",
            started_at=started_at,
            attempt_count=CadJob.attempt_count + 1,
            failure_category=None,
            failure_detail=None,
        )
    )
    if affected_row_count(job_claim) != 1:
        await session.rollback()
        return "already_processed"
    await session.refresh(candidate)
    await session.refresh(job)
    await mark_comparison_batch_running(session, batch_id=candidate.generation_batch_id)
    await session.commit()
    try:
        spec = DesignSpec.model_validate(spec_revision.canonical_spec)
        result = run_isolated_compilation(spec)
        if _validation_has_failure(result.validation_report):
            raise CadCompilationError(
                "The generated candidate failed a deterministic geometry check."
            )
    except CadIsolationError as exc:
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="compiler_isolation_error",
            error=exc,
        )
        return "failed"
    except CadCompilationError as exc:
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="cad_compilation_error",
            error=exc,
        )
        return "failed"
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="unexpected_worker_error",
            error=exc,
        )
        return "failed"
    risk_assessment_id = candidate.risk_assessment_id
    if risk_assessment_id is None:
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="risk_gate_changed",
            error=CadCompilationError("Candidate is missing immutable risk-assessment lineage."),
        )
        return "failed"
    phase5_report, validation_status = normalize_validation_report(
        result.validation_report, risk_assessment_id=risk_assessment_id
    )
    return await _persist_success(
        session,
        candidate,
        job,
        project,
        result,
        spec_revision=spec_revision,
        authorized_plan_id=authorized_plan_id,
        phase5_report=phase5_report,
        validation_status=validation_status,
    )


async def _persist_success(
    session: AsyncSession,
    candidate: CandidateDesign,
    job: CadJob,
    project: Project,
    result: CompilationResult,
    *,
    spec_revision: DesignSpecRevision,
    authorized_plan_id: str | None,
    phase5_report: dict[str, object],
    validation_status: str,
) -> str:
    uploaded_keys: list[str] = []
    artifact_rows: list[CandidateArtifact] = []
    candidate_id = candidate.id
    try:
        # A running native compiler cannot be preempted safely from this process,
        # but the API can record a cooperative cancellation. Refresh before any
        # upload so no private artifact is persisted after that request.
        await session.refresh(candidate)
        await session.refresh(job)
        await session.refresh(project)
        if candidate.status == "cancel_requested" or job.cancel_requested_at is not None:
            await mark_candidate_cancelled(
                session,
                candidate=candidate,
                job=job,
                project=project,
                actor_id="system:cad-worker",
                reason="A cancellation request was observed before artifact persistence.",
            )
            return "cancelled"
        if candidate.status != "running" or job.status != "running":
            return "already_processed"
        if project.status != "generating":
            await _mark_failed(
                session,
                candidate=candidate,
                job=job,
                project=project,
                category="invalid_project_state",
                error=CadCompilationError("The project is no longer generating this candidate."),
            )
            return "failed"
        try:
            await assert_generation_allowed(
                session,
                project=project,
                design_spec=spec_revision,
                expected_assessment_id=candidate.risk_assessment_id,
                authorized_plan_id=authorized_plan_id,
            )
        except RiskGateError as exc:
            await _mark_failed(
                session,
                candidate=candidate,
                job=job,
                project=project,
                category="risk_gate_changed",
                error=CadCompilationError(str(exc)),
            )
            return "failed"
        for kind, content in result.artifacts.items():
            metadata = result.artifact_metadata[kind]
            checksum = metadata["sha256"]
            filename = metadata["filename"]
            content_type = metadata["content_type"]
            size_bytes = metadata["size_bytes"]
            if (
                not isinstance(checksum, str)
                or not isinstance(filename, str)
                or not isinstance(content_type, str)
                or not isinstance(size_bytes, int)
            ):
                raise CadCompilationError("The compiler artifact metadata is invalid.")
            object_key = artifact_object_key(
                project_id=project.id,
                candidate_id=candidate.id,
                checksum_sha256=checksum,
                filename=filename,
            )
            put_private_bytes(object_key=object_key, content=content, content_type=content_type)
            uploaded_keys.append(object_key)
            artifact_rows.append(
                CandidateArtifact(
                    project_id=project.id,
                    candidate_id=candidate.id,
                    kind=kind,
                    filename=filename,
                    content_type=content_type,
                    object_key=object_key,
                    checksum_sha256=checksum,
                    size_bytes=size_bytes,
                )
            )
        # Re-check once the compiler output has been staged but before any
        # artifact metadata can be committed. This narrows the cooperative
        # cancellation window and removes staged private objects on request.
        await session.refresh(candidate)
        await session.refresh(job)
        locked_project = await session.scalar(
            select(Project)
            .where(Project.id == project.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked_project is None:  # pragma: no cover - project deletion is soft-state first
            for object_key in uploaded_keys:
                try:
                    delete_object(object_key=object_key)
                except Exception:
                    pass
            return "already_processed"
        project = locked_project
        if candidate.status == "cancel_requested" or job.cancel_requested_at is not None:
            for object_key in uploaded_keys:
                try:
                    delete_object(object_key=object_key)
                except Exception:
                    pass
            await mark_candidate_cancelled(
                session,
                candidate=candidate,
                job=job,
                project=project,
                actor_id="system:cad-worker",
                reason="A cancellation request was observed before artifact metadata persisted.",
            )
            return "cancelled"
        if candidate.status != "running" or job.status != "running":
            for object_key in uploaded_keys:
                try:
                    delete_object(object_key=object_key)
                except Exception:
                    pass
            return "already_processed"
        if project.status != "generating":
            for object_key in uploaded_keys:
                try:
                    delete_object(object_key=object_key)
                except Exception:
                    pass
            await _mark_failed(
                session,
                candidate=candidate,
                job=job,
                project=project,
                category="invalid_project_state",
                error=CadCompilationError("The project is no longer generating this candidate."),
            )
            return "failed"
        try:
            await assert_generation_allowed(
                session,
                project=project,
                design_spec=spec_revision,
                expected_assessment_id=candidate.risk_assessment_id,
                authorized_plan_id=authorized_plan_id,
            )
        except RiskGateError as exc:
            for object_key in uploaded_keys:
                try:
                    delete_object(object_key=object_key)
                except Exception:
                    pass
            await _mark_failed(
                session,
                candidate=candidate,
                job=job,
                project=project,
                category="risk_gate_changed",
                error=CadCompilationError(str(exc)),
            )
            return "failed"
        provenance_metadata = result.artifact_metadata["provenance_json"]
        provenance_hash = provenance_metadata.get("sha256")
        compiler = result.provenance.get("compiler")
        if not isinstance(provenance_hash, str) or not isinstance(compiler, dict):
            raise CadCompilationError("The compiler provenance is invalid.")
        now = datetime.now(UTC)
        candidate_completion = await session.execute(
            update(CandidateDesign)
            .where(CandidateDesign.id == candidate.id, CandidateDesign.status == "running")
            .values(
                status="succeeded",
                compiler_fingerprint=dict(compiler),
                geometry_summary=result.geometry_summary,
                validation_report=phase5_report,
                validation_status=validation_status,
                provenance_hash=provenance_hash,
                completed_at=now,
            )
        )
        job_completion = await session.execute(
            update(CadJob)
            .where(
                CadJob.id == job.id,
                CadJob.status == "running",
                CadJob.cancel_requested_at.is_(None),
            )
            .values(status="succeeded", completed_at=now)
        )
        if affected_row_count(candidate_completion) != 1 or affected_row_count(job_completion) != 1:
            await session.rollback()
            for object_key in uploaded_keys:
                try:
                    delete_object(object_key=object_key)
                except Exception:
                    pass
            refreshed = await _candidate_and_job(session, candidate_id)
            if refreshed is not None:
                refreshed_candidate, refreshed_job, _, refreshed_project = refreshed
                if (
                    refreshed_candidate.status == "cancel_requested"
                    or refreshed_job.cancel_requested_at is not None
                ):
                    await mark_candidate_cancelled(
                        session,
                        candidate=refreshed_candidate,
                        job=refreshed_job,
                        project=refreshed_project,
                        actor_id="system:cad-worker",
                        reason="A cancellation request won the candidate finalization race.",
                    )
                    return "cancelled"
            return "already_processed"
        await session.refresh(candidate)
        await session.refresh(job)
        session.add_all(artifact_rows)
        session.add(
            CandidateValidationRun(
                project_id=project.id,
                candidate_id=candidate.id,
                risk_assessment_id=candidate.risk_assessment_id,
                design_spec_id=candidate.design_spec_id,
                validator_version=VALIDATOR_VERSION,
                validator_hash=VALIDATOR_HASH,
                input_hash=canonical_hash(
                    {
                        "candidate_id": candidate.id,
                        "risk_assessment_id": candidate.risk_assessment_id,
                        "spec_hash": candidate.spec_hash,
                        "compiler_report": result.validation_report,
                    }
                ),
                overall_status=validation_status,
                report=phase5_report,
                report_hash=canonical_hash(phase5_report),
            )
        )
        if candidate.generation_batch_id is not None:
            await reconcile_comparison_batch(
                session,
                project=project,
                batch_id=candidate.generation_batch_id,
                actor_id="system:cad-worker",
            )
        else:
            transition_project(
                session,
                project,
                target="candidates_ready",
                actor_id="system:cad-worker",
                reason="A deterministic CAD job produced a private immutable candidate bundle.",
                details={"candidate_id": candidate.id, "job_id": job.id},
            )
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id="system:cad-worker",
                event_type="candidate.compiled",
                reason=(
                    "A reviewed deterministic template created a private candidate artifact bundle."
                ),
                details={"candidate_id": candidate.id, "job_id": job.id},
            )
        )
        await session.commit()
        return "succeeded"
    except Exception as exc:
        # A database commit can fail after uploads have completed. Reset the
        # session before recording the durable failure, then reload identities
        # instead of relying on ORM objects invalidated by rollback.
        await session.rollback()
        for object_key in uploaded_keys:
            try:
                delete_object(object_key=object_key)
            except Exception:
                pass
        refreshed = await _candidate_and_job(session, candidate_id)
        if refreshed is None:
            return "failed"
        candidate, job, _, project = refreshed
        await _mark_failed(
            session,
            candidate=candidate,
            job=job,
            project=project,
            category="artifact_storage_error",
            error=exc,
        )
        return "failed"


async def candidate_artifacts(session: AsyncSession, candidate_id: str) -> list[CandidateArtifact]:
    return list(
        (
            await session.scalars(
                select(CandidateArtifact)
                .where(CandidateArtifact.candidate_id == candidate_id)
                .order_by(CandidateArtifact.created_at.asc())
            )
        ).all()
    )


def artifact_kinds(artifacts: Iterable[CandidateArtifact]) -> set[str]:
    return {artifact.kind for artifact in artifacts}
