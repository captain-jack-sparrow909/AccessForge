"""Fail-closed Phase 6 controlled-export, feedback, and review routes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import (
    ApprovalEvent,
    CandidateDesign,
    ControlledPhysicalValidationRecord,
    ExportBundle,
    FeedbackReport,
    TemplateReleaseControl,
)
from accessforge.db.session import get_session
from accessforge.exports.bundle import EXPORT_BUNDLE_FILENAME
from accessforge.exports.protocol import ControlledPhysicalValidationInput, protocol_summary
from accessforge.exports.service import (
    ExportGateError,
    ExportReadiness,
    create_export_approval,
    create_feedback_report,
    create_private_export_bundle,
    create_template_release_control,
    evaluate_export_readiness,
    list_export_bundles,
    load_private_export_bundle_for_download,
    record_controlled_physical_validation,
    report_candidate_hazard,
)
from accessforge.projects.workflow import get_owned_project

router = APIRouter(prefix="/v1", tags=["controlled export and feedback"])


class ControlledExportAcknowledgements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exact_revision_reviewed: bool
    limitations_understood: bool
    non_human_controlled_validation_only: bool


class ExportApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledgement_version: Literal["phase6-controlled-export.v1"]
    acknowledgements: ControlledExportAcknowledgements


class ExportApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    status: str
    acknowledgement_version: str
    approval_hash: str
    approved_at: datetime
    invalidated_at: datetime | None


class PrivateExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_event_id: str = Field(min_length=1, max_length=36)


class PrivateExportBundleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    approval_event_id: str
    filename: str
    status: str
    checksum_sha256: str
    size_bytes: int
    manifest_hash: str
    created_at: datetime
    revoked_at: datetime | None


class ExportReadinessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reasons: list[str]
    acknowledgement_version: str
    risk_input_hash: str | None
    risk_decision_hash: str | None
    validation_report_hash: str | None
    artifact_manifest_hash: str
    artifact_manifest: dict[str, object]
    protocol: dict[str, object]
    limitations: str


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["fit", "comfort", "breakage", "near_miss", "other"]
    severity: Literal["low", "medium", "high"]
    summary: str = Field(min_length=1, max_length=2_000)


class FeedbackRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    candidate_id: str | None
    category: str
    severity: str
    created_at: datetime


class HazardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["high", "critical"]
    summary: str = Field(min_length=1, max_length=2_000)


class HazardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    candidate_id: str
    feedback_report_id: str | None
    status: str
    reported_at: datetime


class ControlledPhysicalValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    protocol_version: str
    record_type: str
    status: str
    recorded_at: datetime


class TemplateReleaseControlCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    template_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    template_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    control_status: Literal["authorized_for_controlled_validation", "quarantined"]
    protocol_version: str | None = Field(default=None, min_length=1, max_length=80)
    evidence_hashes: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(min_length=1, max_length=2_000)


class TemplateReleaseControlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_id: str
    template_version: str
    template_manifest_sha256: str
    status: str
    protocol_version: str | None
    evidence_hashes: list[str]
    control_hash: str
    recorded_at: datetime


async def _owned_candidate(
    session: AsyncSession, *, project_id: str, candidate_id: str
) -> CandidateDesign:
    candidate = await session.scalar(
        select(CandidateDesign).where(
            CandidateDesign.id == candidate_id,
            CandidateDesign.project_id == project_id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return candidate


def _gate_exception(exc: ExportGateError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _readiness_response(readiness: ExportReadiness) -> ExportReadinessRead:
    return ExportReadinessRead(
        allowed=readiness.allowed,
        reasons=list(readiness.reasons),
        acknowledgement_version="phase6-controlled-export.v1",
        risk_input_hash=readiness.risk_input_hash,
        risk_decision_hash=readiness.risk_decision_hash,
        validation_report_hash=readiness.validation_report_hash,
        artifact_manifest_hash=readiness.artifact_manifest_hash,
        artifact_manifest=readiness.artifact_manifest,
        protocol=protocol_summary(),
        limitations=(
            "This route exposes server gate state only. It is not a safety result, fit result, "
            "printability finding, manufacturing approval, or permission for human physical use."
        ),
    )


def _feedback_response(report: FeedbackReport) -> FeedbackRead:
    return FeedbackRead(
        id=report.id,
        candidate_id=report.candidate_id,
        category=report.category,
        severity=report.severity,
        created_at=report.reported_at,
    )


@router.get(
    "/projects/{project_id}/candidates/{candidate_id}/export-readiness",
    response_model=ExportReadinessRead,
)
async def get_export_readiness(
    project_id: str,
    candidate_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ExportReadinessRead:
    project = await get_owned_project(session, principal, project_id)
    candidate = await _owned_candidate(session, project_id=project.id, candidate_id=candidate_id)
    return _readiness_response(
        await evaluate_export_readiness(session, project=project, candidate=candidate)
    )


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}:approve-export",
    response_model=ExportApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
async def approve_export(
    project_id: str,
    candidate_id: str,
    payload: ExportApprovalCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ApprovalEvent:
    project = await get_owned_project(session, principal, project_id)
    candidate = await _owned_candidate(session, project_id=project.id, candidate_id=candidate_id)
    try:
        return await create_export_approval(
            session,
            project=project,
            candidate=candidate,
            idempotency_key=idempotency_key,
            acknowledgement_version=payload.acknowledgement_version,
            acknowledgements=payload.acknowledgements.model_dump(mode="json"),
            actor_id=principal.subject,
        )
    except ExportGateError as exc:
        raise _gate_exception(exc) from exc


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}:export",
    response_model=PrivateExportBundleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_export(
    project_id: str,
    candidate_id: str,
    payload: PrivateExportCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ExportBundle:
    project = await get_owned_project(session, principal, project_id)
    candidate = await _owned_candidate(session, project_id=project.id, candidate_id=candidate_id)
    approval = await session.scalar(
        select(ApprovalEvent).where(
            ApprovalEvent.id == payload.approval_event_id,
            ApprovalEvent.project_id == project.id,
            ApprovalEvent.candidate_id == candidate.id,
        )
    )
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acknowledgement not found for this candidate.",
        )
    try:
        return await create_private_export_bundle(
            session,
            project=project,
            candidate=candidate,
            approval=approval,
            idempotency_key=idempotency_key,
            actor_id=principal.subject,
        )
    except ExportGateError as exc:
        raise _gate_exception(exc) from exc


@router.get(
    "/projects/{project_id}/candidates/{candidate_id}/exports",
    response_model=list[PrivateExportBundleRead],
)
async def get_export_bundles(
    project_id: str,
    candidate_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ExportBundle]:
    project = await get_owned_project(session, principal, project_id)
    await _owned_candidate(session, project_id=project.id, candidate_id=candidate_id)
    return await list_export_bundles(session, project=project, candidate_id=candidate_id)


@router.get(
    "/projects/{project_id}/exports/{bundle_id}/download",
    response_class=Response,
    responses={
        status.HTTP_200_OK: {
            "content": {"application/zip": {}},
            "description": "Authenticated private export bundle.",
        }
    },
)
async def download_private_export(
    project_id: str,
    bundle_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    project = await get_owned_project(session, principal, project_id)
    try:
        _, content = await load_private_export_bundle_for_download(
            session, project=project, bundle_id=bundle_id
        )
    except ExportGateError as exc:
        raise _gate_exception(exc) from exc
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Cache-Control": "no-store, private",
            "Content-Disposition": f'attachment; filename="{EXPORT_BUNDLE_FILENAME}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}/feedback",
    response_model=FeedbackRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    project_id: str,
    candidate_id: str,
    payload: FeedbackCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> FeedbackRead:
    project = await get_owned_project(session, principal, project_id)
    candidate = await _owned_candidate(session, project_id=project.id, candidate_id=candidate_id)
    report = await create_feedback_report(
        session,
        project=project,
        candidate=candidate,
        category=payload.category,
        severity=payload.severity,
        summary=payload.summary.strip(),
        actor_id=principal.subject,
    )
    return _feedback_response(report)


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}:report-hazard",
    response_model=HazardRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_hazard(
    project_id: str,
    candidate_id: str,
    payload: HazardCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> HazardRead:
    project = await get_owned_project(session, principal, project_id)
    candidate = await _owned_candidate(session, project_id=project.id, candidate_id=candidate_id)
    try:
        _, hazard = await report_candidate_hazard(
            session,
            project=project,
            candidate=candidate,
            severity=payload.severity,
            summary=payload.summary.strip(),
            actor_id=principal.subject,
        )
    except ExportGateError as exc:
        raise _gate_exception(exc) from exc
    return HazardRead(
        id=hazard.id,
        candidate_id=hazard.candidate_id,
        feedback_report_id=hazard.feedback_report_id,
        status=hazard.status,
        reported_at=hazard.reported_at,
    )


@router.post(
    "/projects/{project_id}/candidates/{candidate_id}/controlled-validation",
    response_model=ControlledPhysicalValidationRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_controlled_validation(
    project_id: str,
    candidate_id: str,
    payload: ControlledPhysicalValidationInput,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ControlledPhysicalValidationRecord:
    project = await get_owned_project(session, principal, project_id)
    candidate = await _owned_candidate(session, project_id=project.id, candidate_id=candidate_id)
    try:
        return await record_controlled_physical_validation(
            session,
            project=project,
            candidate=candidate,
            payload=payload,
            actor_id=principal.subject,
            actor_role=principal.role,
        )
    except ExportGateError as exc:
        raise _gate_exception(exc) from exc


@router.post(
    "/controlled-validation/template-release-controls",
    response_model=TemplateReleaseControlRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_template_release_control(
    payload: TemplateReleaseControlCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> TemplateReleaseControl:
    try:
        return await create_template_release_control(
            session,
            template_id=payload.template_id,
            template_version=payload.template_version,
            template_manifest_sha256=payload.template_manifest_sha256,
            control_status=payload.control_status,
            protocol_version=payload.protocol_version,
            evidence_hashes=payload.evidence_hashes,
            reason=payload.reason.strip(),
            actor_id=principal.subject,
            actor_role=principal.role,
        )
    except ExportGateError as exc:
        raise _gate_exception(exc) from exc
