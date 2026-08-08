from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import AuditEvent, ConsentRecord, ProjectParticipant, utc_now
from accessforge.db.session import get_session
from accessforge.projects.workflow import get_owned_project, transition_project

router = APIRouter(prefix="/v1/projects/{project_id}/consents", tags=["consent"])

CONSENT_TYPES = {
    "project_text",
    "still_images",
    "video",
    "helper_access",
    "ai_provider_sharing",
    "community_publishing",
    "future_contact",
}


class ConsentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    role: str = Field(pattern="^(participant|co_designer|helper)$")
    relationship_to_user: str | None = Field(default=None, max_length=80)
    choices: dict[str, bool] = Field(min_length=1)
    consent_version: str = Field(default="0.1", min_length=1, max_length=40)

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = set(value) - CONSENT_TYPES
        if unknown:
            raise ValueError(f"Unknown consent choice(s): {', '.join(sorted(unknown))}")
        return value


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_name: str
    role: str
    relationship_to_user: str | None


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    participant_id: str
    consent_type: str
    granted: bool
    consent_version: str
    recorded_at: datetime
    revoked_at: datetime | None


class ConsentResponse(BaseModel):
    participant: ParticipantRead
    records: list[ConsentRead]
    project_status: str


@router.get("", response_model=list[ConsentResponse])
async def list_consents(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ConsentResponse]:
    project = await get_owned_project(session, principal, project_id)
    participants = list(
        (
            await session.scalars(
                select(ProjectParticipant)
                .where(ProjectParticipant.project_id == project.id)
                .order_by(ProjectParticipant.created_at.asc())
            )
        ).all()
    )
    responses: list[ConsentResponse] = []
    for participant in participants:
        records = list(
            (
                await session.scalars(
                    select(ConsentRecord)
                    .where(ConsentRecord.participant_id == participant.id)
                    .order_by(ConsentRecord.recorded_at.asc())
                )
            ).all()
        )
        responses.append(
            ConsentResponse(
                participant=ParticipantRead.model_validate(participant),
                records=[ConsentRead.model_validate(record) for record in records],
                project_status=project.status,
            )
        )
    return responses


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def create_consent(
    project_id: str,
    payload: ConsentCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ConsentResponse:
    project = await get_owned_project(session, principal, project_id)
    if project.status == "blocked_out_of_scope":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This project is outside the supported scope; consent can be saved only before "
                "the boundary is applied."
            ),
        )
    participant = ProjectParticipant(
        project_id=project.id,
        display_name=payload.display_name.strip(),
        role=payload.role,
        relationship_to_user=payload.relationship_to_user,
    )
    session.add(participant)
    await session.flush()
    records = [
        ConsentRecord(
            project_id=project.id,
            participant_id=participant.id,
            consent_type=consent_type,
            granted=granted,
            consent_version=payload.consent_version,
        )
        for consent_type, granted in payload.choices.items()
    ]
    session.add_all(records)
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="consent.recorded",
            reason="Participant consent choices recorded.",
            details={"participant_id": participant.id, "choice_count": len(records)},
        )
    )
    if payload.choices.get("project_text") is True and project.status == "draft":
        if project.scope_status == "blocked":
            transition_project(
                session,
                project,
                target="blocked_out_of_scope",
                actor_id=principal.subject,
                reason=project.scope_reason or "Project failed the deterministic scope pre-screen.",
            )
        else:
            transition_project(
                session,
                project,
                target="consented",
                actor_id=principal.subject,
                reason="Project text consent was granted.",
            )
    await session.commit()
    return ConsentResponse(
        participant=ParticipantRead.model_validate(participant),
        records=[ConsentRead.model_validate(record) for record in records],
        project_status=project.status,
    )


@router.post(
    "/{consent_id}/revoke", response_model=ConsentRead, status_code=status.HTTP_201_CREATED
)
async def revoke_consent(
    project_id: str,
    consent_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ConsentRecord:
    project = await get_owned_project(session, principal, project_id)
    record = await session.scalar(
        select(ConsentRecord).where(
            ConsentRecord.id == consent_id, ConsentRecord.project_id == project.id
        )
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consent record not found."
        )
    if record.revoked_at is not None:
        return record
    record.revoked_at = utc_now()
    replacement = ConsentRecord(
        project_id=project.id,
        participant_id=record.participant_id,
        consent_type=record.consent_type,
        granted=False,
        consent_version=record.consent_version,
    )
    session.add(replacement)
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="consent.revoked",
            reason=f"Consent for {record.consent_type} was revoked.",
            details={"consent_id": record.id},
        )
    )
    if record.consent_type == "project_text" and project.status == "consented":
        transition_project(
            session,
            project,
            target="needs_more_information",
            actor_id=principal.subject,
            reason="Project text consent was revoked.",
        )
    await session.commit()
    await session.refresh(replacement)
    return replacement
