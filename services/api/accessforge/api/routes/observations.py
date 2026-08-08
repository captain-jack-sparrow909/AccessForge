from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import AuditEvent, Observation
from accessforge.db.session import get_session
from accessforge.projects.workflow import get_owned_project, transition_project

router = APIRouter(prefix="/v1/projects/{project_id}/observations", tags=["observations"])


class ObservationCreate(BaseModel):
    text: str = Field(default="", max_length=12000)
    input_mode: str = Field(default="text", pattern="^(text|skipped)$")


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    text: str
    input_mode: str
    source: str
    created_at: datetime
    updated_at: datetime
    version: int


@router.get("", response_model=list[ObservationRead])
async def list_observations(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Observation]:
    project = await get_owned_project(session, principal, project_id)
    result = await session.scalars(
        select(Observation)
        .where(Observation.project_id == project.id)
        .order_by(Observation.created_at.asc())
    )
    return list(result.all())


@router.post("", response_model=ObservationRead, status_code=status.HTTP_201_CREATED)
async def create_observation(
    project_id: str,
    payload: ObservationCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Observation:
    project = await get_owned_project(session, principal, project_id)
    if payload.input_mode == "text" and not payload.text.strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Add a short description or choose skip.")
    observation = Observation(
        project_id=project.id,
        text=payload.text.strip(),
        input_mode=payload.input_mode,
        source="user" if payload.input_mode == "text" else "user_choice",
    )
    session.add(observation)
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="observation.recorded",
            reason="Text observation recorded."
            if payload.input_mode == "text"
            else "Observation skipped by user.",
            details={"observation_id": observation.id, "input_mode": payload.input_mode},
        )
    )
    if project.status in {"consented", "needs_more_information"}:
        transition_project(
            session,
            project,
            target="captured",
            actor_id=principal.subject,
            reason="Observation step completed.",
        )
    await session.commit()
    await session.refresh(observation)
    return observation
