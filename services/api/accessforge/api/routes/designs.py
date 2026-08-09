"""Private immutable DesignSpec and candidate-job API.

Phase 4 intentionally permits users to prepare bounded, provenance-bearing
specifications while keeping compilation behind the future deterministic Phase
5 risk decision.  No request can supply a risk tier or bypass that gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.cad.registry import (
    TemplateRegistryError,
    get_template_release,
    validate_design_spec,
)
from accessforge.cad.schemas import (
    CanonicalLength,
    CreatorType,
    DesignSpec,
    FieldProvenance,
    ManufacturingProfile,
    canonical_length_from_entry,
)
from accessforge.cad.service import candidate_artifacts
from accessforge.cad.units import UnitConversionError
from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import (
    AuditEvent,
    CadJob,
    CandidateDesign,
    DesignSpecRevision,
    Project,
    RequirementRevision,
)
from accessforge.db.results import affected_row_count
from accessforge.db.session import get_session
from accessforge.jobs.tasks import compile_cad_candidate
from accessforge.planning.service import reconcile_comparison_batch
from accessforge.projects.workflow import get_owned_project, transition_project
from accessforge.risk.service import (
    RiskGateError,
    assert_generation_allowed,
    phase6_export_preflight,
)
from accessforge.storage.s3 import presign_download

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["CAD candidates"])


class LengthEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(gt=0, le=100_000)
    unit: Literal["m", "mm", "cm", "in"]
    creator_type: CreatorType = "user"
    source_ref: str = Field(default="user:direct-parameter", min_length=1, max_length=240)
    rationale: str = Field(
        default="Entered directly by the project owner.", min_length=1, max_length=1000
    )

    def canonical_length(self) -> CanonicalLength:
        return canonical_length_from_entry(self.value, self.unit)

    def provenance(self) -> FieldProvenance:
        return FieldProvenance(
            creator_type=self.creator_type, source_ref=self.source_ref, rationale=self.rationale
        )


class ManufacturingProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process: Literal["fdm"]
    material_profile: Literal["pla_provisional", "petg_provisional"]
    nozzle_diameter: LengthEntryInput
    layer_height: LengthEntryInput
    creator_type: CreatorType = "user"
    source_ref: str = Field(default="user:manufacturing-profile", min_length=1, max_length=240)
    rationale: str = Field(
        default="Chosen for a provisional deterministic geometry fixture.",
        min_length=1,
        max_length=1000,
    )

    def canonical_profile(self) -> ManufacturingProfile:
        return ManufacturingProfile(
            process=self.process,
            material_profile=self.material_profile,
            nozzle_diameter=self.nozzle_diameter.canonical_length(),
            layer_height=self.layer_height.canonical_length(),
        )

    def provenance(self) -> FieldProvenance:
        return FieldProvenance(
            creator_type=self.creator_type, source_ref=self.source_ref, rationale=self.rationale
        )


class DesignSpecCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    template_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    parameters: dict[str, LengthEntryInput] = Field(min_length=1, max_length=30)
    manufacturing: ManufacturingProfileInput
    fit_clearance: LengthEntryInput
    dimensional_tolerance: LengthEntryInput
    uses_assessed: list[str] = Field(min_length=1, max_length=20)
    uses_not_assessed: list[str] = Field(min_length=1, max_length=20)
    confirmed_assumptions: list[str] = Field(default_factory=list, max_length=30)
    unresolved_assumptions: list[str] = Field(default_factory=list, max_length=30)
    generation_seed: str = Field(min_length=1, max_length=120)


class DesignSpecRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    revision_number: int
    requirements_revision_id: str
    schema_version: str
    template_id: str
    template_version: str
    template_manifest_sha256: str
    spec_hash: str
    generation_seed: str
    parent_design_spec_id: str | None
    risk_assessment_id: str | None
    canonical_spec: dict[str, object]
    created_at: datetime


class CandidateArtifactRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    filename: str
    content_type: str
    checksum_sha256: str
    size_bytes: int
    created_at: datetime


class CadJobRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    input_hash: str
    attempt_count: int
    failure_category: str | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancel_requested_at: datetime | None
    cancelled_at: datetime | None


class CandidateDesignRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    design_spec_id: str
    risk_assessment_id: str | None
    generation_batch_id: str | None
    variant_key: str | None
    variant_label: str | None
    candidate_number: int
    status: str
    template_id: str
    template_version: str
    template_manifest_sha256: str
    spec_hash: str
    generation_seed: str
    compiler_fingerprint: dict[str, object] | None
    geometry_summary: dict[str, object] | None
    validation_report: dict[str, object] | None
    validation_status: str | None
    provenance_hash: str | None
    failure_category: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    job: CadJobRead | None
    artifacts: list[CandidateArtifactRead]


class GenerateCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_spec_id: str = Field(min_length=1, max_length=36)


class ExportPreflightRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eligible_for_export: bool
    reasons: list[str]
    phase_boundary: str


def _rule_provenance(source_ref: str, rationale: str) -> FieldProvenance:
    return FieldProvenance(creator_type="rule", source_ref=source_ref, rationale=rationale)


def _reviewer_provenance(source_ref: str, rationale: str) -> FieldProvenance:
    return FieldProvenance(creator_type="reviewer", source_ref=source_ref, rationale=rationale)


async def _confirmed_requirement_revision(
    session: AsyncSession, project: Project
) -> RequirementRevision:
    revision_id = project.active_requirement_revision_id
    if revision_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Confirm a requirements revision before preparing a DesignSpec.",
        )
    revision = await session.scalar(
        select(RequirementRevision).where(
            RequirementRevision.id == revision_id,
            RequirementRevision.project_id == project.id,
            RequirementRevision.status == "confirmed",
        )
    )
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The active requirements revision is not a confirmed immutable revision.",
        )
    return revision


def _make_design_spec(
    *,
    project: Project,
    requirements_revision: RequirementRevision,
    payload: DesignSpecCreate,
) -> DesignSpec:
    release = get_template_release(payload.template_id, payload.template_version)
    parameters = {name: entry.canonical_length() for name, entry in payload.parameters.items()}
    provenance: dict[str, FieldProvenance] = {
        "schema_version": _rule_provenance(
            "rule:design-spec-schema-v1",
            "The current DesignSpec schema version is server-controlled.",
        ),
        "project_id": _rule_provenance(
            "project:ownership", "The project ID is anchored by the authenticated route."
        ),
        "requirements_revision_id": _rule_provenance(
            f"requirements:{requirements_revision.id}",
            "The active confirmed requirements revision is anchored by the server.",
        ),
        "template_id": _reviewer_provenance(
            f"template:{release.manifest.template_id}@{release.manifest.version}",
            "Only a repository-reviewed template release may be selected.",
        ),
        "template_version": _reviewer_provenance(
            f"template:{release.manifest.template_id}@{release.manifest.version}",
            "The exact immutable reviewed release is recorded.",
        ),
        "template_manifest_sha256": _reviewer_provenance(
            f"template-manifest:{release.manifest_sha256}",
            "The exact reviewed manifest bytes are recorded.",
        ),
        "manufacturing": payload.manufacturing.provenance(),
        "manufacturing.nozzle_diameter": payload.manufacturing.nozzle_diameter.provenance(),
        "manufacturing.layer_height": payload.manufacturing.layer_height.provenance(),
        "fit_clearance": payload.fit_clearance.provenance(),
        "dimensional_tolerance": payload.dimensional_tolerance.provenance(),
        "uses_assessed": _rule_provenance(
            "user:uses-assessed", "The project owner explicitly listed these assessed uses."
        ),
        "uses_not_assessed": _rule_provenance(
            "user:uses-not-assessed", "The project owner explicitly listed these unassessed uses."
        ),
        "risk_tier": _rule_provenance(
            "rule:phase4-pre-risk-gate", "Phase 4 creates informational R0 specs only."
        ),
        "risk_rule_set_version": _rule_provenance(
            "rule:phase4-pre-risk-gate", "A deterministic R1 decision is deferred to Phase 5."
        ),
        "confirmed_assumptions": _rule_provenance(
            "user:confirmed-assumptions", "The project owner provided these assumptions."
        ),
        "unresolved_assumptions": _rule_provenance(
            "user:unresolved-assumptions", "The project owner kept these assumptions visible."
        ),
        "generation_seed": _rule_provenance(
            "user:generation-seed", "The project owner supplied a deterministic seed label."
        ),
    }
    provenance.update(
        {f"parameters.{name}": entry.provenance() for name, entry in payload.parameters.items()}
    )
    return DesignSpec(
        project_id=project.id,
        requirements_revision_id=requirements_revision.id,
        template_id=release.manifest.template_id,
        template_version=release.manifest.version,
        template_manifest_sha256=release.manifest_sha256,
        parameters=parameters,
        manufacturing=payload.manufacturing.canonical_profile(),
        fit_clearance=payload.fit_clearance.canonical_length(),
        dimensional_tolerance=payload.dimensional_tolerance.canonical_length(),
        uses_assessed=tuple(item.strip() for item in payload.uses_assessed if item.strip()),
        uses_not_assessed=tuple(item.strip() for item in payload.uses_not_assessed if item.strip()),
        risk_tier="R0",
        risk_rule_set_version="phase4-pre-risk-gate.v1",
        confirmed_assumptions=tuple(
            item.strip() for item in payload.confirmed_assumptions if item.strip()
        ),
        unresolved_assumptions=tuple(
            item.strip() for item in payload.unresolved_assumptions if item.strip()
        ),
        generation_seed=payload.generation_seed,
        field_provenance=provenance,
    )


def _spec_read(revision: DesignSpecRevision) -> DesignSpecRead:
    return DesignSpecRead(
        id=revision.id,
        revision_number=revision.revision_number,
        requirements_revision_id=revision.requirements_revision_id,
        schema_version=revision.schema_version,
        template_id=revision.template_id,
        template_version=revision.template_version,
        template_manifest_sha256=revision.template_manifest_sha256,
        spec_hash=revision.spec_hash,
        generation_seed=revision.generation_seed,
        parent_design_spec_id=revision.parent_design_spec_id,
        risk_assessment_id=revision.risk_assessment_id,
        canonical_spec=revision.canonical_spec,
        created_at=revision.created_at,
    )


async def _candidate_read(session: AsyncSession, candidate: CandidateDesign) -> CandidateDesignRead:
    job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate.id))
    artifacts = await candidate_artifacts(session, candidate.id)
    return CandidateDesignRead(
        id=candidate.id,
        design_spec_id=candidate.design_spec_id,
        risk_assessment_id=candidate.risk_assessment_id,
        generation_batch_id=candidate.generation_batch_id,
        variant_key=candidate.variant_key,
        variant_label=candidate.variant_label,
        candidate_number=candidate.candidate_number,
        status=candidate.status,
        template_id=candidate.template_id,
        template_version=candidate.template_version,
        template_manifest_sha256=candidate.template_manifest_sha256,
        spec_hash=candidate.spec_hash,
        generation_seed=candidate.generation_seed,
        compiler_fingerprint=candidate.compiler_fingerprint,
        geometry_summary=candidate.geometry_summary,
        validation_report=candidate.validation_report,
        validation_status=candidate.validation_status,
        provenance_hash=candidate.provenance_hash,
        failure_category=candidate.failure_category,
        created_at=candidate.created_at,
        started_at=candidate.started_at,
        completed_at=candidate.completed_at,
        job=(
            CadJobRead(
                id=job.id,
                status=job.status,
                input_hash=job.input_hash,
                attempt_count=job.attempt_count,
                failure_category=job.failure_category,
                requested_at=job.requested_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                cancel_requested_at=job.cancel_requested_at,
                cancelled_at=job.cancelled_at,
            )
            if job
            else None
        ),
        artifacts=[
            CandidateArtifactRead(
                id=artifact.id,
                kind=artifact.kind,
                filename=artifact.filename,
                content_type=artifact.content_type,
                checksum_sha256=artifact.checksum_sha256,
                size_bytes=artifact.size_bytes,
                created_at=artifact.created_at,
            )
            for artifact in artifacts
        ],
    )


@router.get("/design-specs", response_model=list[DesignSpecRead])
async def list_design_specs(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[DesignSpecRead]:
    project = await get_owned_project(session, principal, project_id)
    revisions = list(
        (
            await session.scalars(
                select(DesignSpecRevision)
                .where(DesignSpecRevision.project_id == project.id)
                .order_by(DesignSpecRevision.revision_number.desc())
            )
        ).all()
    )
    return [_spec_read(revision) for revision in revisions]


@router.post("/design-specs", response_model=DesignSpecRead, status_code=status.HTTP_201_CREATED)
async def create_design_spec(
    project_id: str,
    payload: DesignSpecCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> DesignSpecRead:
    project = await get_owned_project(session, principal, project_id)
    if project.status != "risk_review" or project.scope_status != "supported":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A DesignSpec can be prepared only for a supported project awaiting "
                "deterministic risk review."
            ),
        )
    requirements_revision = await _confirmed_requirement_revision(session, project)
    try:
        spec = _make_design_spec(
            project=project, requirements_revision=requirements_revision, payload=payload
        )
        validate_design_spec(spec)
    except (TemplateRegistryError, UnitConversionError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    next_number = (
        int(
            (
                await session.scalar(
                    select(func.coalesce(func.max(DesignSpecRevision.revision_number), 0)).where(
                        DesignSpecRevision.project_id == project.id
                    )
                )
            )
            or 0
        )
        + 1
    )
    revision = DesignSpecRevision(
        project_id=project.id,
        requirements_revision_id=requirements_revision.id,
        revision_number=next_number,
        schema_version=spec.schema_version,
        template_id=spec.template_id,
        template_version=spec.template_version,
        template_manifest_sha256=spec.template_manifest_sha256,
        canonical_spec=spec.canonical_payload(),
        spec_hash=spec.content_hash,
        generation_seed=spec.generation_seed,
        created_by=principal.subject,
    )
    session.add(revision)
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="design_spec.created",
            reason="User created an immutable canonical DesignSpec from bounded direct parameters.",
            details={
                "design_spec_id": revision.id,
                "requirements_revision_id": requirements_revision.id,
                "template_id": spec.template_id,
                "template_version": spec.template_version,
                "spec_hash": spec.content_hash,
            },
        )
    )
    await session.commit()
    await session.refresh(revision)
    return _spec_read(revision)


@router.get("/design-specs/{design_spec_id}", response_model=DesignSpecRead)
async def get_design_spec(
    project_id: str,
    design_spec_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> DesignSpecRead:
    project = await get_owned_project(session, principal, project_id)
    revision = await session.scalar(
        select(DesignSpecRevision).where(
            DesignSpecRevision.id == design_spec_id,
            DesignSpecRevision.project_id == project.id,
        )
    )
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DesignSpec not found.")
    return _spec_read(revision)


@router.get("/candidates", response_model=list[CandidateDesignRead])
async def list_candidates(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[CandidateDesignRead]:
    project = await get_owned_project(session, principal, project_id)
    candidates = list(
        (
            await session.scalars(
                select(CandidateDesign)
                .where(CandidateDesign.project_id == project.id)
                .order_by(CandidateDesign.candidate_number.desc())
            )
        ).all()
    )
    return [await _candidate_read(session, candidate) for candidate in candidates]


@router.get("/candidates/{candidate_id}", response_model=CandidateDesignRead)
async def get_candidate(
    project_id: str,
    candidate_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> CandidateDesignRead:
    project = await get_owned_project(session, principal, project_id)
    candidate = await session.scalar(
        select(CandidateDesign).where(
            CandidateDesign.id == candidate_id,
            CandidateDesign.project_id == project.id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return await _candidate_read(session, candidate)


@router.get("/candidates/{candidate_id}/preview")
async def get_candidate_preview(
    project_id: str,
    candidate_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Provide a short-lived private GLB URL; this is a viewer input, not export approval."""

    project = await get_owned_project(session, principal, project_id)
    candidate = await session.scalar(
        select(CandidateDesign).where(
            CandidateDesign.id == candidate_id,
            CandidateDesign.project_id == project.id,
            CandidateDesign.status == "succeeded",
        )
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate preview not found.",
        )
    artifacts = await candidate_artifacts(session, candidate.id)
    preview = next((artifact for artifact in artifacts if artifact.kind == "preview_glb"), None)
    if preview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate preview not found.",
        )
    return {
        "preview_url": presign_download(object_key=preview.object_key),
        "content_type": preview.content_type,
    }


@router.post("/candidates/{candidate_id}:export-preflight", response_model=ExportPreflightRead)
async def export_preflight(
    project_id: str,
    candidate_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ExportPreflightRead:
    """Re-run shared gates without exposing an approval or export path in Phase 5."""

    project = await get_owned_project(session, principal, project_id)
    candidate = await session.scalar(
        select(CandidateDesign).where(
            CandidateDesign.id == candidate_id,
            CandidateDesign.project_id == project.id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    _, reasons = await phase6_export_preflight(session, project=project, candidate=candidate)
    return ExportPreflightRead(
        eligible_for_export=False,
        reasons=reasons,
        phase_boundary=(
            "Phase 5 does not approve, export, manufacture, or authorize physical use. "
            "Phase 6 must rerun this gate after explicit approval and controlled validation."
        ),
    )


@router.post("/candidates/{candidate_id}:cancel", response_model=CandidateDesignRead)
async def cancel_candidate(
    project_id: str,
    candidate_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> CandidateDesignRead:
    """Cancel a queued job or request cooperative cancellation before artifact storage."""

    project = await get_owned_project(session, principal, project_id)
    candidate = await session.scalar(
        select(CandidateDesign).where(
            CandidateDesign.id == candidate_id,
            CandidateDesign.project_id == project.id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    job = await session.scalar(select(CadJob).where(CadJob.candidate_id == candidate.id))
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Candidate job is missing."
        )
    now = datetime.now(UTC)
    queued = await session.execute(
        update(CandidateDesign)
        .where(CandidateDesign.id == candidate.id, CandidateDesign.status == "queued")
        .values(status="cancelled", completed_at=now)
    )
    if affected_row_count(queued) == 1:
        job_cancelled = await session.execute(
            update(CadJob)
            .where(CadJob.id == job.id, CadJob.status == "queued")
            .values(
                status="cancelled",
                cancel_requested_at=now,
                cancelled_at=now,
                completed_at=now,
            )
        )
        if affected_row_count(job_cancelled) != 1:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This candidate changed while cancellation was being recorded.",
            )
        if candidate.generation_batch_id is not None:
            await reconcile_comparison_batch(
                session,
                project=project,
                batch_id=candidate.generation_batch_id,
                actor_id=principal.subject,
            )
        elif project.status == "generating":
            transition_project(
                session,
                project,
                target="ready_for_generation",
                actor_id=principal.subject,
                reason="The project owner cancelled a queued private CAD candidate.",
                details={"candidate_id": candidate.id, "job_id": job.id},
            )
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id=principal.subject,
                event_type="candidate.cancelled",
                reason="The project owner cancelled a queued private CAD candidate.",
                details={"candidate_id": candidate.id, "job_id": job.id},
            )
        )
        await session.commit()
        await session.refresh(candidate)
        return await _candidate_read(session, candidate)
    running = await session.execute(
        update(CandidateDesign)
        .where(CandidateDesign.id == candidate.id, CandidateDesign.status == "running")
        .values(status="cancel_requested")
    )
    if affected_row_count(running) == 1:
        job_requested = await session.execute(
            update(CadJob)
            .where(
                CadJob.id == job.id,
                CadJob.status == "running",
                CadJob.cancel_requested_at.is_(None),
            )
            .values(cancel_requested_at=now)
        )
        if affected_row_count(job_requested) != 1:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This candidate changed while cancellation was being recorded.",
            )
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id=principal.subject,
                event_type="candidate.cancel_requested",
                reason="The project owner requested cooperative cancellation of a running CAD job.",
                details={"candidate_id": candidate.id, "job_id": job.id},
            )
        )
        await session.commit()
        await session.refresh(candidate)
        return await _candidate_read(session, candidate)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="This candidate is already terminal or cannot be cancelled in its current state.",
    )


@router.post(
    "/candidates:generate",
    response_model=CandidateDesignRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_candidate(
    project_id: str,
    payload: GenerateCandidateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> CandidateDesignRead:
    project = await get_owned_project(session, principal, project_id)
    spec_revision = await session.scalar(
        select(DesignSpecRevision).where(
            DesignSpecRevision.id == payload.design_spec_id,
            DesignSpecRevision.project_id == project.id,
        )
    )
    if spec_revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DesignSpec not found.")
    existing = await session.scalar(
        select(CadJob).where(
            CadJob.project_id == project.id, CadJob.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        candidate = await session.scalar(
            select(CandidateDesign).where(CandidateDesign.id == existing.candidate_id)
        )
        if candidate is None or existing.input_hash != spec_revision.spec_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This idempotency key was already used for a different candidate request.",
            )
        if existing.status == "queued" and candidate.status == "queued":
            try:
                compile_cad_candidate.delay(candidate.id)
            except Exception:
                # The durable queued row is picked up by the periodic dispatcher.
                pass
        return await _candidate_read(session, candidate)
    requirements_revision = await _confirmed_requirement_revision(session, project)
    if requirements_revision.id != spec_revision.requirements_revision_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The DesignSpec is based on an older requirements revision and must be recreated."
            ),
        )
    try:
        spec = DesignSpec.model_validate(spec_revision.canonical_spec)
        validate_design_spec(spec)
    except (TemplateRegistryError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The immutable DesignSpec can no longer be resolved to its "
                "reviewed template release."
            ),
        ) from exc
    if project.status != "ready_for_generation" or project.scope_status != "supported":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Candidate compilation is unavailable until Phase 5 records a "
                "current deterministic "
                "R1 risk decision."
            ),
        )
    try:
        assessment = await assert_generation_allowed(
            session, project=project, design_spec=spec_revision
        )
    except RiskGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    next_number = (
        int(
            (
                await session.scalar(
                    select(func.coalesce(func.max(CandidateDesign.candidate_number), 0)).where(
                        CandidateDesign.project_id == project.id
                    )
                )
            )
            or 0
        )
        + 1
    )
    candidate = CandidateDesign(
        project_id=project.id,
        design_spec_id=spec_revision.id,
        risk_assessment_id=assessment.id,
        candidate_number=next_number,
        template_id=spec.template_id,
        template_version=spec.template_version,
        template_manifest_sha256=spec.template_manifest_sha256,
        spec_hash=spec.content_hash,
        generation_seed=spec.generation_seed,
    )
    session.add(candidate)
    await session.flush()
    job = CadJob(
        project_id=project.id,
        candidate_id=candidate.id,
        idempotency_key=idempotency_key,
        input_hash=spec.content_hash,
        requested_by=principal.subject,
    )
    session.add(job)
    transition_project(
        session,
        project,
        target="generating",
        actor_id=principal.subject,
        reason="A bounded deterministic CAD candidate was queued from an immutable DesignSpec.",
        details={
            "candidate_id": candidate.id,
            "design_spec_id": spec_revision.id,
            "job_id": job.id,
        },
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="candidate.queued",
            reason="A private deterministic CAD candidate was queued.",
            details={
                "candidate_id": candidate.id,
                "job_id": job.id,
                "design_spec_id": spec_revision.id,
            },
        )
    )
    await session.commit()
    try:
        compile_cad_candidate.delay(candidate.id)
    except Exception as exc:
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id="system:cad-api",
                event_type="candidate.queue_submission_deferred",
                reason=(
                    "The broker publish was uncertain, so the durable private candidate remains "
                    "queued for idempotent recovery."
                ),
                details={
                    "candidate_id": candidate.id,
                    "job_id": job.id,
                    "error": str(exc).replace("\n", " ")[:500],
                },
            )
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The private candidate is durably queued and will be retried by the background "
                "dispatcher. No export or approval occurred."
            ),
        ) from exc
    return await _candidate_read(session, candidate)
