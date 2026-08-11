from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import (
    AuditEvent,
    CadJob,
    CandidateDesign,
    DeletionJob,
    Project,
    utc_now,
)
from accessforge.db.results import affected_row_count
from accessforge.db.session import get_session
from accessforge.projects.workflow import (
    ensure_user,
    evaluate_scope,
    get_owned_project,
    transition_project,
)
from accessforge.risk.service import invalidate_active_risk_assessment

router = APIRouter(prefix="/v1/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    goal: str | None = Field(default=None, max_length=5000)
    object_description: str | None = Field(default=None, max_length=5000)
    action_description: str | None = Field(default=None, max_length=5000)
    environment: str | None = Field(default=None, max_length=5000)
    load_context: str | None = Field(default=None, max_length=80)
    safety_system: bool | None = None
    age_context: str | None = Field(default=None, max_length=80)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    goal: str | None = Field(default=None, max_length=5000)
    object_description: str | None = Field(default=None, max_length=5000)
    action_description: str | None = Field(default=None, max_length=5000)
    environment: str | None = Field(default=None, max_length=5000)
    load_context: str | None = Field(default=None, max_length=80)
    safety_system: bool | None = None
    age_context: str | None = Field(default=None, max_length=80)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    goal: str | None
    object_description: str | None
    action_description: str | None
    environment: str | None
    load_context: str | None
    safety_system: bool | None
    age_context: str | None
    scope_status: str
    scope_reason: str | None
    model_provider_config_id: str | None
    active_requirement_revision_id: str | None
    active_risk_assessment_id: str | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class DeletionStatusRead(BaseModel):
    """Owner-visible, sanitized progress for a soft-deleted private project."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    requested_at: datetime
    attempt_count: int
    started_at: datetime | None
    next_attempt_at: datetime | None
    last_error_code: str | None
    last_error_at: datetime | None
    reconciliation_passes: int
    last_reconciled_at: datetime | None
    completed_at: datetime | None


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Project]:
    result = await session.execute(
        select(Project)
        .where(Project.owner_id == principal.subject, Project.status != "deleted")
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Project:
    await ensure_user(session, principal)
    scope_status, scope_reason = evaluate_scope(
        action=payload.action_description,
        object_description=payload.object_description,
        environment=payload.environment,
        load_context=payload.load_context,
        safety_system=payload.safety_system,
        age_context=payload.age_context,
    )
    project = Project(
        owner_id=principal.subject,
        name=payload.name.strip(),
        description=payload.description,
        goal=payload.goal,
        object_description=payload.object_description,
        action_description=payload.action_description,
        environment=payload.environment,
        load_context=payload.load_context,
        safety_system=payload.safety_system,
        age_context=payload.age_context,
        scope_status=scope_status,
        scope_reason=scope_reason,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Project:
    return await get_owned_project(session, principal, project_id)


@router.get("/{project_id}/deletion-status", response_model=DeletionStatusRead)
async def get_deletion_status(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> DeletionJob:
    """Expose only safe cleanup progress to the owner after a soft delete."""

    await get_owned_project(session, principal, project_id, include_deleted=True)
    deletion_job = await session.scalar(
        select(DeletionJob)
        .where(DeletionJob.project_id == project_id)
        .order_by(DeletionJob.requested_at.desc(), DeletionJob.id.desc())
    )
    if deletion_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deletion status not found."
        )
    return deletion_job


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await get_owned_project(session, principal, project_id)
    risk_relevant_fields = {
        "description",
        "goal",
        "object_description",
        "action_description",
        "environment",
        "load_context",
        "safety_system",
        "age_context",
    }
    if project.status == "generating" and risk_relevant_fields.intersection(
        payload.model_fields_set
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancel or wait for the CAD job before changing a risk-relevant project fact.",
        )
    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.description is not None:
        project.description = payload.description
    for field in (
        "goal",
        "object_description",
        "action_description",
        "environment",
        "load_context",
        "safety_system",
        "age_context",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(project, field, value)
    project.scope_status, project.scope_reason = evaluate_scope(
        action=project.action_description,
        object_description=project.object_description,
        environment=project.environment,
        load_context=project.load_context,
        safety_system=project.safety_system,
        age_context=project.age_context,
    )
    project.updated_at = utc_now()
    project.version += 1
    if risk_relevant_fields.intersection(payload.model_fields_set):
        await invalidate_active_risk_assessment(
            session,
            project=project,
            actor_id=principal.subject,
            reason="A project fact used by the deterministic risk assessment changed.",
        )
    await session.commit()
    await session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_project(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    # This row lock is the common write barrier shared with server-side CAD
    # and export persistence. Once deletion owns it, no new private object can
    # be staged from those paths before the deleted state is committed.
    project = await session.scalar(
        select(Project)
        .where(Project.id == project_id, Project.owner_id == principal.subject)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    existing_job = await session.scalar(
        select(DeletionJob)
        .where(DeletionJob.project_id == project.id)
        .order_by(DeletionJob.requested_at.desc(), DeletionJob.id.desc())
    )
    if project.status == "deleted" and existing_job is not None:
        # Repeated owner requests must not create duplicate object-cleanup
        # outboxes. The status endpoint remains the source of safe progress.
        return {"project_id": project.id, "status": "deletion_queued"}
    if project.status != "deleted":
        transition_project(
            session,
            project,
            target="deleted",
            actor_id=principal.subject,
            reason="User requested project deletion.",
        )
        cancellation_requested_at = datetime.now(UTC)
        queued_candidates = await session.execute(
            update(CandidateDesign)
            .where(
                CandidateDesign.project_id == project.id,
                CandidateDesign.status == "queued",
            )
            .values(status="cancelled", completed_at=cancellation_requested_at)
        )
        running_candidates = await session.execute(
            update(CandidateDesign)
            .where(
                CandidateDesign.project_id == project.id,
                CandidateDesign.status == "running",
            )
            .values(status="cancel_requested")
        )
        queued_jobs = await session.execute(
            update(CadJob)
            .where(CadJob.project_id == project.id, CadJob.status == "queued")
            .values(
                status="cancelled",
                cancel_requested_at=cancellation_requested_at,
                cancelled_at=cancellation_requested_at,
                completed_at=cancellation_requested_at,
            )
        )
        running_jobs = await session.execute(
            update(CadJob)
            .where(CadJob.project_id == project.id, CadJob.status == "running")
            .values(cancel_requested_at=cancellation_requested_at)
        )
        cancelled_count = affected_row_count(queued_candidates) + affected_row_count(queued_jobs)
        in_flight_count = affected_row_count(running_candidates) + affected_row_count(running_jobs)
        if cancelled_count or in_flight_count:
            session.add(
                AuditEvent(
                    project_id=project.id,
                    actor_id=principal.subject,
                    event_type="deletion.private_writes_fenced",
                    reason=(
                        "Project deletion cancelled queued CAD work and requested cooperative "
                        "cancellation of in-flight private writes."
                    ),
                    details={
                        "terminal_updates": cancelled_count,
                        "in_flight_updates": in_flight_count,
                    },
                )
            )
    resolved_project_id = project.id
    try:
        deletion_job = DeletionJob(project_id=resolved_project_id, requested_by=principal.subject)
        session.add(deletion_job)
        # The partial unique index can raise here, before commit, when two
        # initial DELETE requests race. Keep flush inside the same recovery
        # path as commit so both callers receive the idempotent 202 result.
        await session.flush()
        session.add(
            AuditEvent(
                project_id=resolved_project_id,
                actor_id=principal.subject,
                event_type="deletion.queued",
                reason="The owner requested durable private-object cleanup after soft deletion.",
                details={"deletion_job_id": deletion_job.id},
            )
        )
        await session.commit()
    except IntegrityError:
        # A concurrent request may have committed the only active cleanup job
        # after this request read the project. Roll back and report the durable
        # idempotent result rather than queueing a second cleanup path.
        await session.rollback()
        existing_job = await session.scalar(
            select(DeletionJob)
            .where(DeletionJob.project_id == resolved_project_id)
            .order_by(DeletionJob.requested_at.desc(), DeletionJob.id.desc())
        )
        if existing_job is None:
            raise
    return {"project_id": resolved_project_id, "status": "deletion_queued"}
