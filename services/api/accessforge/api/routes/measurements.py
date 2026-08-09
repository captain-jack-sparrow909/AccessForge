from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import AuditEvent, Measurement, utc_now
from accessforge.db.session import get_session
from accessforge.projects.workflow import get_owned_project
from accessforge.risk.service import invalidate_active_risk_assessment

router = APIRouter(prefix="/v1/projects/{project_id}/measurements", tags=["measurements"])

UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4}


def to_mm(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    try:
        multiplier = UNIT_TO_MM[unit]
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="Unit must be mm, cm, or in.") from exc
    return value * multiplier


class MeasurementCreate(BaseModel):
    kind: str = Field(min_length=1, max_length=80)
    value: float | None = Field(default=None, ge=0)
    unit: str = Field(default="mm", pattern="^(mm|cm|in)$")
    tolerance: float | None = Field(default=None, ge=0)
    method: str = Field(default="ruler", pattern="^(ruler|caliper|visual_estimate|other)$")
    confirmed: bool = False
    unknown: bool = False
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_known_value(self) -> "MeasurementCreate":
        if self.unknown and self.value is not None:
            raise ValueError("An unknown measurement cannot include a value.")
        if not self.unknown and self.value is None:
            raise ValueError("Add a value or mark the measurement as unknown.")
        if self.unknown and self.confirmed:
            raise ValueError("An unknown measurement cannot be confirmed.")
        return self


class MeasurementUpdate(BaseModel):
    value: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, pattern="^(mm|cm|in)$")
    tolerance: float | None = Field(default=None, ge=0)
    method: str | None = Field(default=None, pattern="^(ruler|caliper|visual_estimate|other)$")
    confirmed: bool | None = None
    unknown: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    value: float | None
    unit: str
    canonical_value_mm: float | None
    tolerance: float | None
    canonical_tolerance_mm: float | None
    method: str
    source: str
    confirmed: bool
    unknown: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
    version: int


async def get_measurement(
    project_id: str, measurement_id: str, principal: Principal, session: AsyncSession
) -> Measurement:
    project = await get_owned_project(session, principal, project_id)
    if project.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancel or wait for the CAD job before changing a risk-relevant measurement.",
        )
    measurement = await session.scalar(
        select(Measurement).where(
            Measurement.id == measurement_id, Measurement.project_id == project.id
        )
    )
    if measurement is None:
        raise HTTPException(status_code=404, detail="Measurement not found.")
    return measurement


@router.get("", response_model=list[MeasurementRead])
async def list_measurements(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Measurement]:
    project = await get_owned_project(session, principal, project_id)
    result = await session.scalars(
        select(Measurement)
        .where(Measurement.project_id == project.id)
        .order_by(Measurement.created_at.asc())
    )
    return list(result.all())


@router.post("", response_model=MeasurementRead, status_code=status.HTTP_201_CREATED)
async def create_measurement(
    project_id: str,
    payload: MeasurementCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Measurement:
    project = await get_owned_project(session, principal, project_id)
    if project.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancel or wait for the CAD job before changing a risk-relevant measurement.",
        )
    measurement = Measurement(
        project_id=project.id,
        kind=payload.kind.strip(),
        value=payload.value,
        unit=payload.unit,
        canonical_value_mm=to_mm(payload.value, payload.unit),
        tolerance=payload.tolerance,
        canonical_tolerance_mm=to_mm(payload.tolerance, payload.unit),
        method=payload.method,
        confirmed=payload.confirmed,
        unknown=payload.unknown,
        notes=payload.notes,
    )
    session.add(measurement)
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="measurement.recorded",
            reason="Manual measurement recorded.",
            details={"measurement_id": measurement.id, "unknown": payload.unknown},
        )
    )
    await invalidate_active_risk_assessment(
        session,
        project=project,
        actor_id=principal.subject,
        reason="A measurement used by deterministic risk and DesignSpec provenance was recorded.",
    )
    await session.commit()
    await session.refresh(measurement)
    return measurement


@router.patch("/{measurement_id}", response_model=MeasurementRead)
async def update_measurement(
    project_id: str,
    measurement_id: str,
    payload: MeasurementUpdate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Measurement:
    project = await get_owned_project(session, principal, project_id)
    if project.status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancel or wait for the CAD job before changing a risk-relevant measurement.",
        )
    measurement = await get_measurement(project_id, measurement_id, principal, session)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(measurement, key, value)
    if measurement.unknown:
        if measurement.value is not None or measurement.confirmed:
            raise HTTPException(
                status_code=422,
                detail="Unknown measurements cannot include a value or be confirmed.",
            )
        measurement.value = None
    elif measurement.value is None:
        raise HTTPException(status_code=422, detail="Add a value or mark the measurement unknown.")
    if measurement.unit not in UNIT_TO_MM:
        raise HTTPException(status_code=422, detail="Unit must be mm, cm, or in.")
    measurement.canonical_value_mm = to_mm(measurement.value, measurement.unit)
    measurement.canonical_tolerance_mm = to_mm(measurement.tolerance, measurement.unit)
    measurement.updated_at = utc_now()
    measurement.version += 1
    session.add(
        AuditEvent(
            project_id=measurement.project_id,
            actor_id=principal.subject,
            event_type="measurement.updated",
            reason="Manual measurement updated.",
            details={"measurement_id": measurement.id},
        )
    )
    await invalidate_active_risk_assessment(
        session,
        project=project,
        actor_id=principal.subject,
        reason="A measurement used by deterministic risk and DesignSpec provenance changed.",
    )
    await session.commit()
    await session.refresh(measurement)
    return measurement
