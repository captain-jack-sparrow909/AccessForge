from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import Project, utc_now
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
    project = await get_owned_project(session, principal, project_id)
    transition_project(
        session,
        project,
        target="deleted",
        actor_id=principal.subject,
        reason="User requested project deletion.",
    )
    from accessforge.db.models import DeletionJob

    session.add(DeletionJob(project_id=project.id, requested_by=principal.subject))
    await session.commit()
    return {"project_id": project.id, "status": "deletion_queued"}
