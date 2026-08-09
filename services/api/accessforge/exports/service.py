"""Fail-closed Phase 6 controlled export, feedback, and recall services.

Every path in this module is intentionally conservative.  A user acknowledgement
is never a professional, safety, manufacturing, or physical-use approval.  The
current repository releases remain blocked by default because no qualified
controlled-validation evidence/control is present.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.cad.registry import TemplateRegistryError, TemplateRelease, get_template_release
from accessforge.cad.schemas import DesignSpec, canonical_hash
from accessforge.cad.service import candidate_artifacts
from accessforge.core.config import Settings, get_settings
from accessforge.db.models import (
    ApprovalEvent,
    AuditEvent,
    CandidateArtifact,
    CandidateDesign,
    CandidateGenerationBatch,
    CandidateValidationRun,
    ControlledPhysicalValidationRecord,
    DesignPlan,
    DesignSpecRevision,
    ExportBundle,
    ExportValidationRun,
    FeedbackReport,
    HazardReport,
    Project,
    RequirementRevision,
    RiskAssessment,
    RiskAssessmentContext,
    TemplateReleaseControl,
)
from accessforge.exports.bundle import (
    EXPORT_BUNDLE_FILENAME,
    BundleArtifact,
    ExportBundleError,
    build_export_bundle,
    verify_export_bundle,
)
from accessforge.exports.protocol import (
    CONTROLLED_VALIDATION_PROTOCOL_VERSION,
    ControlledPhysicalValidationInput,
    recorded_result,
)
from accessforge.projects.workflow import transition_project
from accessforge.risk.private_context import (
    RiskContextSealError,
    context_hash,
    open_risk_context,
)
from accessforge.risk.schemas import RiskDecision
from accessforge.risk.service import (
    RiskGateError,
    current_confirmed_requirements,
    evaluate_project_risk,
    get_current_risk_assessment,
    invalidate_active_risk_assessment,
    invalidate_project_export_authorizations,
)
from accessforge.storage.s3 import (
    delete_object,
    get_private_bytes,
    put_private_bytes,
)

_REQUIRED_ARTIFACT_FILENAMES: dict[str, str] = {
    "design_step": "design.step",
    "design_stl": "design.stl",
    "preview_glb": "preview.glb",
    "design_spec_json": "design-spec.json",
    "validation_report_json": "validation-report.json",
    "readme_txt": "README.txt",
    "provenance_json": "provenance.json",
}
_OPTIONAL_ARTIFACT_FILENAMES: dict[str, str] = {"design_3mf": "design.3mf"}
_CONTROL_STATUS_AUTHORIZED = "authorized_for_controlled_validation"
_CONTROL_STATUS_QUARANTINED = "quarantined"
_ACTIVE_HAZARD_STATUSES = {"reported", "under_review"}
_ACKNOWLEDGEMENT_VERSION = "phase6-controlled-export.v1"
_FEEDBACK_CATEGORIES = {"fit", "comfort", "breakage", "near_miss", "other"}
_FEEDBACK_SEVERITIES = {"low", "medium", "high"}
_HAZARD_SEVERITIES = {"high", "critical"}


class ExportGateError(ValueError):
    """A candidate cannot proceed through a Phase 6 controlled-export boundary."""


@dataclass(frozen=True)
class ExportLineage:
    project: Project
    candidate: CandidateDesign
    assessment: RiskAssessment
    requirements_revision: RequirementRevision
    design_spec: DesignSpecRevision
    validation: CandidateValidationRun
    plan: DesignPlan
    batch: CandidateGenerationBatch
    release: TemplateRelease


@dataclass(frozen=True)
class ExportReadiness:
    allowed: bool
    reasons: tuple[str, ...]
    lineage: ExportLineage | None
    risk_input_hash: str | None
    risk_decision_hash: str | None
    validation_report_hash: str | None
    artifact_manifest: dict[str, object]
    artifact_manifest_hash: str


async def evaluate_export_readiness(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
    settings: Settings | None = None,
) -> ExportReadiness:
    """Evaluate every server-owned Phase 6 gate without trusting browser state."""

    reasons: list[str] = []
    artifact_manifest, artifact_manifest_hash, artifact_reasons = await _artifact_manifest(
        session, candidate=candidate
    )
    reasons.extend(artifact_reasons)
    try:
        lineage = await _load_export_lineage(session, project=project, candidate=candidate)
    except ExportGateError as exc:
        reasons.append(str(exc))
        return _readiness(
            reasons=reasons,
            lineage=None,
            artifact_manifest=artifact_manifest,
            artifact_manifest_hash=artifact_manifest_hash,
        )

    runtime_settings = settings or get_settings()
    try:
        risk_input_hash, risk_decision_hash, decision = await _revalidate_current_risk(
            session, lineage=lineage, settings=runtime_settings
        )
    except ExportGateError as exc:
        reasons.append(str(exc))
        risk_input_hash = None
        risk_decision_hash = None
        decision = None
    if decision is not None and decision.tier != "R1":
        reasons.append("Fresh deterministic risk revalidation does not permit a controlled export.")

    if lineage.validation.overall_status != "passed":
        reasons.append(
            "Deterministic validation contains failed, unassessed, or confirmation-needed checks."
        )
    if not runtime_settings.phase6_controlled_validation_enabled:
        reasons.append("Controlled physical-validation recording is disabled by deployment policy.")
    if not runtime_settings.phase6_export_enabled:
        reasons.append("Private controlled export is disabled by deployment policy.")
    await _append_control_and_evidence_reasons(
        session,
        lineage=lineage,
        reasons=reasons,
    )
    return _readiness(
        reasons=reasons,
        lineage=lineage,
        risk_input_hash=risk_input_hash,
        risk_decision_hash=risk_decision_hash,
        validation_report_hash=lineage.validation.report_hash,
        artifact_manifest=artifact_manifest,
        artifact_manifest_hash=artifact_manifest_hash,
    )


async def create_export_approval(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
    idempotency_key: str,
    acknowledgement_version: str,
    acknowledgements: dict[str, object],
    actor_id: str,
) -> ApprovalEvent:
    """Persist a user acknowledgement only after a fresh server gate passes."""

    existing = await session.scalar(
        select(ApprovalEvent).where(
            ApprovalEvent.project_id == project.id,
            ApprovalEvent.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.candidate_id != candidate.id:
            raise ExportGateError(
                "This idempotency key was already used for a different candidate."
            )
        return existing
    project, candidate = await _lock_project_and_candidate(
        session, project_id=project.id, candidate_id=candidate.id
    )
    readiness = await evaluate_export_readiness(session, project=project, candidate=candidate)
    validation_run = await _record_export_validation(
        session, readiness=readiness, boundary="approval"
    )
    if not readiness.allowed or validation_run is None or readiness.lineage is None:
        await _record_gate_denial(
            session,
            project=project,
            candidate=candidate,
            boundary="approval",
            reasons=readiness.reasons,
            actor_id=actor_id,
        )
        await session.commit()
        raise ExportGateError(_first_reason(readiness.reasons))
    if acknowledgement_version != _ACKNOWLEDGEMENT_VERSION:
        raise ExportGateError(
            "The acknowledgement copy is not the current controlled-export version."
        )
    _validate_acknowledgements(acknowledgements)
    lineage = readiness.lineage
    approval_hash = canonical_hash(
        {
            "acknowledgement_version": acknowledgement_version,
            "acknowledgements": acknowledgements,
            "artifact_manifest_hash": readiness.artifact_manifest_hash,
            "candidate_id": candidate.id,
            "design_spec_hash": lineage.design_spec.spec_hash,
            "risk_decision_hash": readiness.risk_decision_hash,
            "template_manifest_sha256": lineage.release.manifest_sha256,
            "validation_report_hash": lineage.validation.report_hash,
        }
    )
    approval = ApprovalEvent(
        id=str(uuid4()),
        project_id=project.id,
        candidate_id=candidate.id,
        design_plan_id=lineage.plan.id,
        generation_batch_id=lineage.batch.id,
        requirements_revision_id=lineage.requirements_revision.id,
        risk_assessment_id=lineage.assessment.id,
        design_spec_id=lineage.design_spec.id,
        export_validation_run_id=validation_run.id,
        idempotency_key=idempotency_key,
        acknowledgement_version=acknowledgement_version,
        acknowledgements=acknowledgements,
        risk_decision_hash=_required_hash(readiness.risk_decision_hash),
        design_spec_hash=lineage.design_spec.spec_hash,
        template_manifest_sha256=lineage.release.manifest_sha256,
        validation_report_hash=lineage.validation.report_hash,
        artifact_manifest_hash=readiness.artifact_manifest_hash,
        approval_hash=approval_hash,
        approved_by=actor_id,
    )
    session.add(approval)
    if project.status == "user_review":
        transition_project(
            session,
            project,
            target="approved",
            actor_id=actor_id,
            reason=(
                "The project owner acknowledged the exact private candidate bundle for the "
                "controlled-export gate; no safety or physical-use approval was recorded."
            ),
            details={"approval_event_id": approval.id, "candidate_id": candidate.id},
        )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="export.approval_recorded",
            reason="A user acknowledgement was bound to exact immutable controlled-export lineage.",
            details={"approval_event_id": approval.id, "candidate_id": candidate.id},
        )
    )
    await session.commit()
    await session.refresh(approval)
    return approval


async def create_private_export_bundle(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
    approval: ApprovalEvent,
    idempotency_key: str,
    actor_id: str,
) -> ExportBundle:
    """Revalidate, verify artifact bytes, and atomically record a private ZIP.

    Current repository templates do not satisfy the controlled-validation gate,
    so normal deployments stop before object reads or ZIP creation.  The bundle
    path is nevertheless fully validated for a future independently reviewed
    release/control; it never trusts stored hashes without reading the bytes.
    """

    existing = await session.scalar(
        select(ExportBundle).where(
            ExportBundle.project_id == project.id,
            ExportBundle.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.candidate_id != candidate.id or existing.approval_event_id != approval.id:
            raise ExportGateError("This idempotency key was already used for a different export.")
        return existing
    project, candidate = await _lock_project_and_candidate(
        session, project_id=project.id, candidate_id=candidate.id
    )
    existing_for_approval = await session.scalar(
        select(ExportBundle).where(
            ExportBundle.project_id == project.id,
            ExportBundle.candidate_id == candidate.id,
            ExportBundle.approval_event_id == approval.id,
            ExportBundle.status == "ready",
            ExportBundle.revoked_at.is_(None),
        )
    )
    if existing_for_approval is not None:
        return existing_for_approval
    approval = await _active_approval(
        session, project=project, candidate=candidate, approval_id=approval.id
    )
    readiness = await evaluate_export_readiness(session, project=project, candidate=candidate)
    validation_run = await _record_export_validation(
        session, readiness=readiness, boundary="export"
    )
    approval_reasons = _approval_match_reasons(approval=approval, readiness=readiness)
    if approval_reasons:
        readiness = ExportReadiness(
            allowed=False,
            reasons=tuple(dict.fromkeys([*readiness.reasons, *approval_reasons])),
            lineage=readiness.lineage,
            risk_input_hash=readiness.risk_input_hash,
            risk_decision_hash=readiness.risk_decision_hash,
            validation_report_hash=readiness.validation_report_hash,
            artifact_manifest=readiness.artifact_manifest,
            artifact_manifest_hash=readiness.artifact_manifest_hash,
        )
    if not readiness.allowed or validation_run is None or readiness.lineage is None:
        await _record_gate_denial(
            session,
            project=project,
            candidate=candidate,
            boundary="export",
            reasons=readiness.reasons,
            actor_id=actor_id,
        )
        await session.commit()
        raise ExportGateError(_first_reason(readiness.reasons))
    try:
        artifact_bytes = await _load_verified_artifact_bytes(session, candidate=candidate)
        payload = build_export_bundle(
            artifacts=artifact_bytes,
            report_text=_plain_language_export_report(readiness.lineage, readiness),
            print_guidance=dict(readiness.lineage.release.manifest.print_guidance),
            lineage=_bundle_lineage(readiness.lineage, readiness, approval),
        )
        bundle_is_valid, bundle_errors = verify_export_bundle(payload.content)
        if not bundle_is_valid:
            raise ExportBundleError(
                "The assembled private ZIP failed its own fixed-layout verification: "
                + "; ".join(bundle_errors)
            )
    except (BotoCoreError, ClientError, ExportBundleError, OSError, ValueError) as exc:
        await _record_gate_denial(
            session,
            project=project,
            candidate=candidate,
            boundary="export",
            reasons=("The immutable candidate artifacts could not be verified for export.",),
            actor_id=actor_id,
        )
        await session.commit()
        raise ExportGateError(
            "The immutable candidate artifacts could not be verified for export."
        ) from exc
    bundle_id = str(uuid4())
    bundle = ExportBundle(
        id=bundle_id,
        project_id=project.id,
        candidate_id=candidate.id,
        approval_event_id=approval.id,
        export_validation_run_id=validation_run.id,
        idempotency_key=idempotency_key,
        filename=EXPORT_BUNDLE_FILENAME,
        object_key=_export_object_key(
            project_id=project.id,
            candidate_id=candidate.id,
            bundle_id=bundle_id,
            checksum_sha256=payload.checksum_sha256,
        ),
        checksum_sha256=payload.checksum_sha256,
        size_bytes=len(payload.content),
        manifest=payload.manifest,
        manifest_hash=payload.manifest_hash,
    )
    try:
        put_private_bytes(
            object_key=bundle.object_key,
            content=payload.content,
            content_type="application/zip",
        )
        session.add(bundle)
        if project.status == "approved":
            transition_project(
                session,
                project,
                target="export_ready",
                actor_id=actor_id,
                reason="A revalidated private controlled-validation ZIP was recorded.",
                details={"candidate_id": candidate.id, "export_bundle_id": bundle.id},
            )
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id=actor_id,
                event_type="export.bundle_recorded",
                reason="A private ZIP was assembled after fresh deterministic revalidation.",
                details={"candidate_id": candidate.id, "export_bundle_id": bundle.id},
            )
        )
        await session.commit()
    except Exception:
        try:
            delete_object(object_key=bundle.object_key)
        except Exception:
            pass
        raise
    await session.refresh(bundle)
    return bundle


async def load_private_export_bundle_for_download(
    session: AsyncSession,
    *,
    project: Project,
    bundle_id: str,
) -> tuple[ExportBundle, bytes]:
    """Read a private ZIP only after a fresh authenticated server recheck.

    The API route streams these bytes to the authenticated caller rather than
    returning an independently reusable object-store bearer URL.  The caller's
    access token is therefore rechecked at every delivery attempt.
    """

    bundle = await session.scalar(
        select(ExportBundle).where(
            ExportBundle.id == bundle_id,
            ExportBundle.project_id == project.id,
            ExportBundle.status == "ready",
            ExportBundle.revoked_at.is_(None),
        )
    )
    if bundle is None:
        raise ExportGateError("The private export bundle is unavailable.")
    approval = await session.scalar(
        select(ApprovalEvent).where(
            ApprovalEvent.id == bundle.approval_event_id,
            ApprovalEvent.project_id == project.id,
            ApprovalEvent.status == "active",
            ApprovalEvent.invalidated_at.is_(None),
        )
    )
    if approval is None:
        raise ExportGateError("The export acknowledgement is no longer current for this bundle.")
    candidate = await session.scalar(
        select(CandidateDesign).where(
            CandidateDesign.id == bundle.candidate_id,
            CandidateDesign.project_id == project.id,
        )
    )
    if candidate is None:
        raise ExportGateError("The private export bundle no longer has a valid candidate lineage.")
    # A prior bundle record is never a standing authorization. Policy toggles,
    # hazards, reviewer controls, evidence changes, and stale lineage must all
    # be re-evaluated before delivery.
    readiness = await evaluate_export_readiness(session, project=project, candidate=candidate)
    if not readiness.allowed:
        raise ExportGateError(_first_reason(readiness.reasons))
    approval_reasons = _approval_match_reasons(approval=approval, readiness=readiness)
    if approval_reasons:
        raise ExportGateError(_first_reason(tuple(approval_reasons)))
    return bundle, await _verify_recorded_bundle_bytes(bundle)


async def list_export_bundles(
    session: AsyncSession, *, project: Project, candidate_id: str
) -> list[ExportBundle]:
    return list(
        (
            await session.scalars(
                select(ExportBundle)
                .where(
                    ExportBundle.project_id == project.id,
                    ExportBundle.candidate_id == candidate_id,
                )
                .order_by(ExportBundle.created_at.desc())
            )
        ).all()
    )


async def create_feedback_report(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign | None,
    category: str,
    severity: str,
    summary: str,
    actor_id: str,
) -> FeedbackReport:
    """Record private typed feedback without treating it as a safety conclusion."""

    if candidate is not None and candidate.project_id != project.id:
        raise ExportGateError("The feedback candidate does not belong to this project.")
    if category not in _FEEDBACK_CATEGORIES or severity not in _FEEDBACK_SEVERITIES:
        raise ExportGateError("The private feedback category or severity is unsupported.")
    normalized_summary = summary.strip()
    if not normalized_summary or len(normalized_summary) > 2_000:
        raise ExportGateError("A concise private feedback observation is required.")
    report = FeedbackReport(
        project_id=project.id,
        candidate_id=candidate.id if candidate else None,
        category=category,
        severity=severity,
        summary=normalized_summary,
        reported_by=actor_id,
    )
    session.add(report)
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="feedback.recorded",
            reason="A private typed candidate feedback record was created.",
            details={
                "feedback_report_id": report.id,
                "candidate_id": candidate.id if candidate else None,
                "category": category,
                "severity": severity,
            },
        )
    )
    await session.commit()
    await session.refresh(report)
    return report


async def report_candidate_hazard(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
    severity: str,
    summary: str,
    actor_id: str,
) -> tuple[FeedbackReport, HazardReport]:
    """Create a local hazard block and invalidate current export authorization.

    A project report cannot globally quarantine a template by itself: that would
    permit one account to deny service to every other project.  A separately
    authorized reviewer control can do that after review.
    """

    if candidate.project_id != project.id:
        raise ExportGateError("The hazardous-result candidate does not belong to this project.")
    if severity not in _HAZARD_SEVERITIES:
        raise ExportGateError("The hazardous-result severity is unsupported.")
    normalized_summary = summary.strip()
    if not normalized_summary or len(normalized_summary) > 2_000:
        raise ExportGateError("A concise hazardous-result observation is required.")
    feedback = FeedbackReport(
        project_id=project.id,
        candidate_id=candidate.id,
        category="hazard",
        severity=severity,
        summary=normalized_summary,
        reported_by=actor_id,
    )
    session.add(feedback)
    await session.flush()
    hazard = HazardReport(
        project_id=project.id,
        candidate_id=candidate.id,
        feedback_report_id=feedback.id,
        template_id=candidate.template_id,
        template_version=candidate.template_version,
        template_manifest_sha256=candidate.template_manifest_sha256,
        reported_by=actor_id,
    )
    session.add(hazard)
    await invalidate_active_risk_assessment(
        session,
        project=project,
        actor_id=actor_id,
        reason="A hazardous-result report requires renewed deterministic review before any export.",
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="hazard.reported",
            reason="A private hazardous-result report blocked the candidate's export path.",
            details={
                "hazard_report_id": hazard.id,
                "candidate_id": candidate.id,
                "severity": severity,
            },
        )
    )
    await session.commit()
    await session.refresh(feedback)
    await session.refresh(hazard)
    return feedback, hazard


async def record_controlled_physical_validation(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
    payload: ControlledPhysicalValidationInput,
    actor_id: str,
    actor_role: str,
    settings: Settings | None = None,
) -> ControlledPhysicalValidationRecord:
    """Record reviewer evidence for a non-human fixture/coupon protocol only."""

    runtime_settings = settings or get_settings()
    _require_controlled_validation_reviewer(actor_role, runtime_settings)
    if not runtime_settings.phase6_controlled_validation_enabled:
        raise ExportGateError(
            "Controlled physical-validation recording is disabled by deployment policy."
        )
    if candidate.project_id != project.id:
        raise ExportGateError(
            "The controlled-validation candidate does not belong to this project."
        )
    if candidate.status != "succeeded":
        raise ExportGateError("A controlled record requires a successfully compiled candidate.")
    try:
        release = get_template_release(candidate.template_id, candidate.template_version)
    except TemplateRegistryError as exc:
        raise ExportGateError("The candidate's reviewed template release is unavailable.") from exc
    if release.manifest_sha256 != candidate.template_manifest_sha256:
        raise ExportGateError("The candidate does not match its reviewed template release.")
    controls = list(
        (
            await session.scalars(
                select(TemplateReleaseControl).where(
                    TemplateReleaseControl.template_id == candidate.template_id,
                    TemplateReleaseControl.template_version == candidate.template_version,
                    TemplateReleaseControl.template_manifest_sha256
                    == candidate.template_manifest_sha256,
                )
            )
        ).all()
    )
    if any(control.status == _CONTROL_STATUS_QUARANTINED for control in controls):
        raise ExportGateError("This reviewed template release is quarantined.")
    if not any(
        control.status == _CONTROL_STATUS_AUTHORIZED
        and control.protocol_version == CONTROLLED_VALIDATION_PROTOCOL_VERSION
        and bool(control.evidence_hashes)
        and all(_is_sha256(value) for value in control.evidence_hashes)
        for control in controls
    ):
        raise ExportGateError(
            "A current reviewer release control is required before recording this evidence."
        )
    document = DesignSpec.model_validate(
        (await _candidate_design_spec(session, candidate)).canonical_spec
    )
    process = payload.process_record
    if (
        document.manufacturing.process != process.process
        or document.manufacturing.material_profile != process.material_profile
    ):
        raise ExportGateError(
            "The controlled record must use the candidate's recorded process profile."
        )
    result = recorded_result(payload)
    record = ControlledPhysicalValidationRecord(
        project_id=project.id,
        candidate_id=candidate.id,
        template_id=candidate.template_id,
        template_version=candidate.template_version,
        template_manifest_sha256=candidate.template_manifest_sha256,
        protocol_version=payload.protocol_version,
        record_type=payload.record_type,
        process_record=process.model_dump(mode="json"),
        measured_dimensions=[
            {
                **item.model_dump(mode="json"),
                "within_recorded_tolerance": item.within_recorded_tolerance,
            }
            for item in payload.measured_dimensions
        ],
        stop_criteria_observed=list(payload.stop_criteria_observed),
        evidence_hashes=list(payload.evidence_hashes),
        status=result,
        recorded_by=actor_id,
    )
    session.add(record)
    invalidated_approvals = await invalidate_project_export_authorizations(
        session,
        project=project,
        actor_id=actor_id,
        reason=(
            "A controlled-validation observation changed the evidence available for this "
            "project, so any earlier export acknowledgement must be renewed."
        ),
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="controlled_validation.recorded",
            reason="A reviewer recorded non-human fixture/coupon evidence without a safety claim.",
            details={
                "candidate_id": candidate.id,
                "controlled_validation_record_id": record.id,
                "record_type": record.record_type,
                "status": record.status,
                "evidence_count": len(record.evidence_hashes),
                "invalidated_approval_count": invalidated_approvals,
            },
        )
    )
    await session.commit()
    await session.refresh(record)
    return record


async def create_template_release_control(
    session: AsyncSession,
    *,
    template_id: str,
    template_version: str,
    template_manifest_sha256: str,
    control_status: str,
    protocol_version: str | None,
    evidence_hashes: list[str],
    reason: str,
    actor_id: str,
    actor_role: str,
    settings: Settings | None = None,
) -> TemplateReleaseControl:
    """Add an immutable reviewer release control or quarantine record."""

    runtime_settings = settings or get_settings()
    _require_controlled_validation_reviewer(actor_role, runtime_settings)
    if not runtime_settings.phase6_controlled_validation_enabled:
        raise ExportGateError("Template release controls are disabled by deployment policy.")
    if control_status not in {_CONTROL_STATUS_AUTHORIZED, _CONTROL_STATUS_QUARANTINED}:
        raise ExportGateError("The template release control status is unsupported.")
    try:
        release = get_template_release(template_id, template_version)
    except TemplateRegistryError as exc:
        raise ExportGateError("The requested template release is not repository reviewed.") from exc
    if release.manifest_sha256 != template_manifest_sha256:
        raise ExportGateError(
            "The requested template release hash does not match the reviewed release."
        )
    if control_status == _CONTROL_STATUS_AUTHORIZED and (
        protocol_version != CONTROLLED_VALIDATION_PROTOCOL_VERSION or not evidence_hashes
    ):
        raise ExportGateError(
            "A controlled-validation authorization needs current protocol evidence."
        )
    if not all(_is_sha256(value) for value in evidence_hashes):
        raise ExportGateError(
            "Template release control evidence hashes must be lowercase SHA-256 values."
        )
    control_hash = canonical_hash(
        {
            "evidence_hashes": evidence_hashes,
            "protocol_version": protocol_version,
            "reason": reason,
            "status": control_status,
            "template_id": template_id,
            "template_manifest_sha256": template_manifest_sha256,
            "template_version": template_version,
        }
    )
    control = TemplateReleaseControl(
        template_id=template_id,
        template_version=template_version,
        template_manifest_sha256=template_manifest_sha256,
        status=control_status,
        protocol_version=protocol_version,
        evidence_hashes=evidence_hashes,
        reason=reason,
        control_hash=control_hash,
        recorded_by=actor_id,
    )
    session.add(control)
    await _invalidate_release_approvals(
        session,
        template_manifest_sha256=template_manifest_sha256,
        actor_id=actor_id,
        reason=(
            "A reviewer quarantined this template release after a safety concern."
            if control_status == _CONTROL_STATUS_QUARANTINED
            else "A reviewer recorded new template-release control evidence, so exact "
            "export acknowledgements must be renewed."
        ),
    )
    await session.commit()
    await session.refresh(control)
    return control


async def _load_export_lineage(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
) -> ExportLineage:
    """Resolve the complete immutable lineage required by the export boundary."""

    if candidate.project_id != project.id:
        raise ExportGateError("The candidate does not belong to this project.")
    if project.scope_status != "supported":
        raise ExportGateError("The project is not inside the supported deterministic MVP scope.")
    if project.status not in {"user_review", "approved", "export_ready"}:
        raise ExportGateError("The project is not at the controlled-export review boundary.")
    if candidate.status != "succeeded":
        raise ExportGateError("Only a successfully compiled private candidate can be considered.")
    if candidate.risk_assessment_id is None:
        raise ExportGateError(
            "The candidate is not bound to an immutable deterministic risk decision."
        )

    assessment = await get_current_risk_assessment(session, project)
    if assessment is None or assessment.id != candidate.risk_assessment_id:
        raise ExportGateError(
            "The candidate is not bound to the current deterministic risk decision."
        )
    if assessment.tier != "R1":
        raise ExportGateError("Only a current deterministic R1 decision can reach this boundary.")
    if assessment.status != "current":
        raise ExportGateError("The candidate's deterministic risk decision is no longer current.")
    try:
        requirements = await current_confirmed_requirements(session, project)
    except RiskGateError as exc:
        raise ExportGateError(
            "The project has no current confirmed requirements for controlled export."
        ) from exc
    if requirements.id != assessment.requirements_revision_id:
        raise ExportGateError("The risk decision no longer matches confirmed requirements.")

    specification = await _candidate_design_spec(session, candidate)
    if (
        specification.project_id != project.id
        or specification.requirements_revision_id != requirements.id
        or specification.risk_assessment_id != assessment.id
    ):
        raise ExportGateError(
            "The candidate's immutable DesignSpec does not match current project lineage."
        )
    try:
        document = DesignSpec.model_validate(specification.canonical_spec)
        release = get_template_release(document.template_id, document.template_version)
        if document.template_manifest_sha256 != release.manifest_sha256:
            raise ExportGateError("The DesignSpec no longer matches its reviewed template release.")
    except (TemplateRegistryError, ValueError) as exc:
        if isinstance(exc, ExportGateError):
            raise
        raise ExportGateError("The candidate's reviewed template release is unavailable.") from exc
    if (
        document.risk_tier != "R1"
        or document.risk_rule_set_version != assessment.ruleset_version
        or document.unresolved_assumptions
    ):
        raise ExportGateError("The immutable DesignSpec is not a complete current R1 input.")
    if (
        candidate.template_id != document.template_id
        or candidate.template_version != document.template_version
        or candidate.template_manifest_sha256 != document.template_manifest_sha256
        or candidate.spec_hash != specification.spec_hash
        or candidate.generation_seed != document.generation_seed
    ):
        raise ExportGateError("The candidate metadata does not match its immutable DesignSpec.")

    validation = await session.scalar(
        select(CandidateValidationRun)
        .where(
            CandidateValidationRun.project_id == project.id,
            CandidateValidationRun.candidate_id == candidate.id,
        )
        .order_by(CandidateValidationRun.created_at.desc(), CandidateValidationRun.id.desc())
    )
    if validation is None:
        raise ExportGateError(
            "No immutable deterministic validation run is recorded for this candidate."
        )
    if (
        validation.design_spec_id != specification.id
        or validation.risk_assessment_id != assessment.id
        or validation.report_hash != canonical_hash(validation.report)
        or validation.overall_status != validation.report.get("overall_status")
    ):
        raise ExportGateError("The candidate's deterministic validation lineage is inconsistent.")

    if candidate.generation_batch_id is None:
        raise ExportGateError("The candidate has no bounded comparison-batch lineage.")
    batch = await session.scalar(
        select(CandidateGenerationBatch).where(
            CandidateGenerationBatch.id == candidate.generation_batch_id,
            CandidateGenerationBatch.project_id == project.id,
        )
    )
    if batch is None or batch.risk_assessment_id != assessment.id:
        raise ExportGateError(
            "The candidate's comparison batch does not match its current risk lineage."
        )
    if batch.status not in {"completed", "completed_with_failures"} or batch.completed_at is None:
        raise ExportGateError("The private comparison batch is not complete.")
    plan = await session.scalar(
        select(DesignPlan).where(
            DesignPlan.id == batch.design_plan_id,
            DesignPlan.project_id == project.id,
            DesignPlan.risk_assessment_id == assessment.id,
        )
    )
    if (
        plan is None
        or plan.status != "comparison_selected"
        or plan.selected_candidate_id != candidate.id
    ):
        raise ExportGateError("The candidate has not been explicitly selected from its comparison.")
    return ExportLineage(
        project=project,
        candidate=candidate,
        assessment=assessment,
        requirements_revision=requirements,
        design_spec=specification,
        validation=validation,
        plan=plan,
        batch=batch,
        release=release,
    )


async def _candidate_design_spec(
    session: AsyncSession, candidate: CandidateDesign
) -> DesignSpecRevision:
    specification = await session.scalar(
        select(DesignSpecRevision).where(DesignSpecRevision.id == candidate.design_spec_id)
    )
    if specification is None:
        raise ExportGateError("The candidate's immutable DesignSpec is unavailable.")
    return specification


async def _artifact_manifest(
    session: AsyncSession, *, candidate: CandidateDesign
) -> tuple[dict[str, object], str, list[str]]:
    """Normalize artifact metadata without leaking private object keys."""

    expected = {**_REQUIRED_ARTIFACT_FILENAMES, **_OPTIONAL_ARTIFACT_FILENAMES}
    artifacts = await candidate_artifacts(session, candidate.id)
    reasons: list[str] = []
    by_kind: dict[str, CandidateArtifact] = {}
    for artifact in artifacts:
        if artifact.project_id != candidate.project_id or artifact.candidate_id != candidate.id:
            reasons.append("Candidate artifact ownership metadata is inconsistent.")
            continue
        if artifact.kind not in expected:
            reasons.append("The candidate includes an undeclared export artifact kind.")
            continue
        if artifact.kind in by_kind:
            reasons.append("The candidate includes duplicate export artifact kinds.")
            continue
        if artifact.filename != expected[artifact.kind]:
            reasons.append("A candidate artifact filename does not match the fixed export layout.")
            continue
        if not _is_sha256(artifact.checksum_sha256) or artifact.size_bytes < 0:
            reasons.append("A candidate artifact has invalid immutable checksum metadata.")
            continue
        by_kind[artifact.kind] = artifact
    missing = sorted(set(_REQUIRED_ARTIFACT_FILENAMES) - set(by_kind))
    if missing:
        reasons.append("The candidate is missing required immutable export artifacts.")
    manifest: dict[str, object] = {
        "schema_version": "phase6-artifact-manifest.v1",
        "candidate_id": candidate.id,
        "candidate_spec_hash": candidate.spec_hash,
        "artifacts": [
            {
                "kind": kind,
                "filename": artifact.filename,
                "content_type": artifact.content_type,
                "checksum_sha256": artifact.checksum_sha256,
                "size_bytes": artifact.size_bytes,
            }
            for kind, artifact in sorted(by_kind.items())
        ],
    }
    return manifest, canonical_hash(manifest), list(dict.fromkeys(reasons))


async def _revalidate_current_risk(
    session: AsyncSession,
    *,
    lineage: ExportLineage,
    settings: Settings,
) -> tuple[str, str, RiskDecision]:
    """Rerun deterministic risk logic from sealed server-held context only."""

    if not settings.risk_context_encryption_key:
        raise ExportGateError(
            "Private risk-context revalidation is not configured by deployment policy."
        )
    stored_context = await session.scalar(
        select(RiskAssessmentContext).where(
            RiskAssessmentContext.risk_assessment_id == lineage.assessment.id
        )
    )
    if stored_context is None:
        raise ExportGateError("The immutable risk context is unavailable for fresh revalidation.")
    if stored_context.envelope_version != "afrc1":
        raise ExportGateError(
            "The immutable risk context uses an unsupported revalidation envelope."
        )
    try:
        context = open_risk_context(
            stored_context.encrypted_context,
            key=settings.risk_context_encryption_key,
            project_id=lineage.project.id,
            assessment_id=lineage.assessment.id,
        )
    except RiskContextSealError as exc:
        raise ExportGateError(
            "The immutable risk context cannot be authenticated for revalidation."
        ) from exc
    if context_hash(context) != stored_context.context_hash:
        raise ExportGateError("The immutable risk context checksum does not verify.")
    snapshot_context = lineage.assessment.input_snapshot.get("risk_context")
    retained_context = context.model_dump(mode="json")
    retained_intended_use = retained_context.pop("intended_use", None)
    if not isinstance(retained_intended_use, str):  # pragma: no cover - typed context guard
        raise ExportGateError("The immutable risk context is malformed.")
    retained_context["intended_use_hash"] = hashlib.sha256(
        retained_intended_use.encode("utf-8")
    ).hexdigest()
    if (
        not isinstance(snapshot_context, dict)
        or canonical_hash(retained_context) != canonical_hash(snapshot_context)
    ):
        raise ExportGateError("The immutable risk context does not match the recorded assessment.")
    try:
        fresh = await evaluate_project_risk(
            session,
            project=lineage.project,
            requirements_revision=lineage.requirements_revision,
            source_spec=lineage.design_spec,
            context=context,
        )
    except RiskGateError as exc:
        raise ExportGateError("Fresh deterministic risk revalidation could not complete.") from exc
    decision = fresh.decision
    if (
        decision.ruleset_version != lineage.assessment.ruleset_version
        or decision.ruleset_hash != lineage.assessment.ruleset_hash
    ):
        raise ExportGateError("The deterministic risk ruleset changed after candidate generation.")
    decision_hash = canonical_hash(
        {
            "allowed_actions": list(decision.allowed_actions),
            "input_hash": fresh.input_hash,
            "matched_findings": [
                item.model_dump(mode="json") for item in decision.matched_findings
            ],
            "ruleset_hash": decision.ruleset_hash,
            "ruleset_version": decision.ruleset_version,
            "tier": decision.tier,
            "unresolved_questions": list(decision.unresolved_questions),
        }
    )
    return fresh.input_hash, decision_hash, decision


async def _append_control_and_evidence_reasons(
    session: AsyncSession,
    *,
    lineage: ExportLineage,
    reasons: list[str],
) -> None:
    """Require reviewed release control and non-human evidence without claims."""

    hazards = list(
        (
            await session.scalars(
                select(HazardReport).where(
                    HazardReport.project_id == lineage.project.id,
                    HazardReport.candidate_id == lineage.candidate.id,
                    HazardReport.status.in_(_ACTIVE_HAZARD_STATUSES),
                )
            )
        ).all()
    )
    if hazards:
        reasons.append(
            "A hazardous-result report must be reviewed before this candidate can proceed."
        )

    controls = list(
        (
            await session.scalars(
                select(TemplateReleaseControl)
                .where(
                    TemplateReleaseControl.template_id == lineage.candidate.template_id,
                    TemplateReleaseControl.template_version == lineage.candidate.template_version,
                    TemplateReleaseControl.template_manifest_sha256
                    == lineage.candidate.template_manifest_sha256,
                )
                .order_by(
                    TemplateReleaseControl.recorded_at.desc(), TemplateReleaseControl.id.desc()
                )
            )
        ).all()
    )
    if any(control.status == _CONTROL_STATUS_QUARANTINED for control in controls):
        reasons.append("This reviewed template release is quarantined and cannot be exported.")
    has_release_control = any(
        control.status == _CONTROL_STATUS_AUTHORIZED
        and control.protocol_version == CONTROLLED_VALIDATION_PROTOCOL_VERSION
        and bool(control.evidence_hashes)
        and all(_is_sha256(value) for value in control.evidence_hashes)
        for control in controls
    )
    if not has_release_control:
        reasons.append(
            "This template release lacks current reviewer-controlled validation evidence."
        )

    records = list(
        (
            await session.scalars(
                select(ControlledPhysicalValidationRecord)
                .where(
                    ControlledPhysicalValidationRecord.project_id == lineage.project.id,
                    ControlledPhysicalValidationRecord.candidate_id == lineage.candidate.id,
                    ControlledPhysicalValidationRecord.template_manifest_sha256
                    == lineage.candidate.template_manifest_sha256,
                    ControlledPhysicalValidationRecord.protocol_version
                    == CONTROLLED_VALIDATION_PROTOCOL_VERSION,
                )
                .order_by(
                    ControlledPhysicalValidationRecord.recorded_at.desc(),
                    ControlledPhysicalValidationRecord.id.desc(),
                )
            )
        ).all()
    )
    if any(record.status == "stopped_for_recorded_criterion" for record in records):
        reasons.append("A controlled-validation record has a stop criterion requiring review.")
    if any(record.status == "outside_recorded_tolerance" for record in records):
        reasons.append(
            "A controlled-validation record is outside its recorded tolerance and requires review."
        )
    completed_types = {
        record.record_type
        for record in records
        if record.status == "within_recorded_tolerance"
        and bool(record.evidence_hashes)
        and all(_is_sha256(value) for value in record.evidence_hashes)
    }
    if {"dimensional_fixture", "physical_coupon"} - completed_types:
        reasons.append(
            "Current non-human dimensional-fixture and physical-coupon records are required."
        )


def _readiness(
    *,
    reasons: list[str],
    lineage: ExportLineage | None,
    artifact_manifest: dict[str, object],
    artifact_manifest_hash: str,
    risk_input_hash: str | None = None,
    risk_decision_hash: str | None = None,
    validation_report_hash: str | None = None,
) -> ExportReadiness:
    deduplicated = tuple(dict.fromkeys(reason for reason in reasons if reason))
    allowed = (
        lineage is not None
        and not deduplicated
        and risk_input_hash is not None
        and risk_decision_hash is not None
        and validation_report_hash is not None
    )
    return ExportReadiness(
        allowed=allowed,
        reasons=deduplicated,
        lineage=lineage,
        risk_input_hash=risk_input_hash,
        risk_decision_hash=risk_decision_hash,
        validation_report_hash=validation_report_hash,
        artifact_manifest=artifact_manifest,
        artifact_manifest_hash=artifact_manifest_hash,
    )


async def _record_export_validation(
    session: AsyncSession, *, readiness: ExportReadiness, boundary: str
) -> ExportValidationRun | None:
    """Persist a fresh Phase 6 recheck when complete lineage exists."""

    if (
        readiness.lineage is None
        or readiness.risk_input_hash is None
        or readiness.risk_decision_hash is None
        or readiness.validation_report_hash is None
    ):
        return None
    lineage = readiness.lineage
    record = ExportValidationRun(
        project_id=lineage.project.id,
        candidate_id=lineage.candidate.id,
        risk_assessment_id=lineage.assessment.id,
        design_spec_id=lineage.design_spec.id,
        validation_run_id=lineage.validation.id,
        boundary=boundary,
        risk_input_hash=readiness.risk_input_hash,
        risk_decision_hash=readiness.risk_decision_hash,
        validation_report_hash=readiness.validation_report_hash,
        artifact_manifest=readiness.artifact_manifest,
        artifact_manifest_hash=readiness.artifact_manifest_hash,
        status="passed" if readiness.allowed else "blocked",
        reasons=list(readiness.reasons),
    )
    session.add(record)
    await session.flush()
    return record


async def _record_gate_denial(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
    boundary: str,
    reasons: tuple[str, ...],
    actor_id: str,
) -> None:
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type=f"export.{boundary}_denied",
            reason="A fail-closed controlled-export gate denied the current candidate.",
            details={
                "candidate_id": candidate.id,
                "boundary": boundary,
                "reason_count": len(reasons),
                "reasons": list(reasons)[:10],
            },
        )
    )


async def _lock_project_and_candidate(
    session: AsyncSession, *, project_id: str, candidate_id: str
) -> tuple[Project, CandidateDesign]:
    project = await session.scalar(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    candidate = await session.scalar(
        select(CandidateDesign)
        .where(CandidateDesign.id == candidate_id, CandidateDesign.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if project is None or candidate is None:
        raise ExportGateError("The project or candidate is unavailable for controlled export.")
    return project, candidate


async def _active_approval(
    session: AsyncSession,
    *,
    project: Project,
    candidate: CandidateDesign,
    approval_id: str,
) -> ApprovalEvent:
    approval = await session.scalar(
        select(ApprovalEvent)
        .where(
            ApprovalEvent.id == approval_id,
            ApprovalEvent.project_id == project.id,
            ApprovalEvent.candidate_id == candidate.id,
            ApprovalEvent.status == "active",
            ApprovalEvent.invalidated_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if approval is None:
        raise ExportGateError("A current acknowledgement for this exact candidate is required.")
    return approval


def _approval_match_reasons(*, approval: ApprovalEvent, readiness: ExportReadiness) -> list[str]:
    if readiness.lineage is None:
        return [
            "The acknowledgement cannot be matched because current export lineage is unavailable."
        ]
    lineage = readiness.lineage
    expected = {
        "candidate_id": lineage.candidate.id,
        "design_plan_id": lineage.plan.id,
        "generation_batch_id": lineage.batch.id,
        "requirements_revision_id": lineage.requirements_revision.id,
        "risk_assessment_id": lineage.assessment.id,
        "design_spec_id": lineage.design_spec.id,
        "risk_decision_hash": readiness.risk_decision_hash,
        "design_spec_hash": lineage.design_spec.spec_hash,
        "template_manifest_sha256": lineage.release.manifest_sha256,
        "validation_report_hash": lineage.validation.report_hash,
        "artifact_manifest_hash": readiness.artifact_manifest_hash,
        "acknowledgement_version": _ACKNOWLEDGEMENT_VERSION,
    }
    reasons: list[str] = []
    for field, expected_value in expected.items():
        if expected_value is None or getattr(approval, field) != expected_value:
            reasons.append(
                "The acknowledgement does not match the current immutable export lineage."
            )
            break
    if approval.status != "active" or approval.invalidated_at is not None:
        reasons.append("The acknowledgement is no longer active.")
    try:
        _validate_acknowledgements(approval.acknowledgements)
    except ExportGateError:
        reasons.append("The acknowledgement record is incomplete.")
    return list(dict.fromkeys(reasons))


async def _load_verified_artifact_bytes(
    session: AsyncSession, *, candidate: CandidateDesign
) -> list[BundleArtifact]:
    manifest, _, reasons = await _artifact_manifest(session, candidate=candidate)
    if reasons:
        raise ExportBundleError(
            "Candidate artifact metadata is not eligible for a fixed export bundle."
        )
    artifact_values = manifest.get("artifacts")
    if not isinstance(artifact_values, list):  # pragma: no cover - manifest is built above
        raise ExportBundleError("Candidate artifact metadata is malformed.")
    metadata = {
        artifact.kind: artifact for artifact in await candidate_artifacts(session, candidate.id)
    }
    bundles: list[BundleArtifact] = []
    maximum = min(get_settings().asset_max_bytes, 50_000_000)
    for item in artifact_values:
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str):
            raise ExportBundleError("Candidate artifact metadata is malformed.")
        artifact = metadata.get(item["kind"])
        if artifact is None:  # pragma: no cover - checked by _artifact_manifest
            raise ExportBundleError("Candidate artifact metadata changed during export.")
        content = get_private_bytes(object_key=artifact.object_key, max_bytes=maximum)
        if len(content) != artifact.size_bytes:
            raise ExportBundleError("A candidate artifact size does not match immutable metadata.")
        if hashlib.sha256(content).hexdigest() != artifact.checksum_sha256:
            raise ExportBundleError("A candidate artifact hash does not match immutable metadata.")
        bundles.append(
            BundleArtifact(
                kind=artifact.kind,
                filename=artifact.filename,
                checksum_sha256=artifact.checksum_sha256,
                size_bytes=artifact.size_bytes,
                content=content,
            )
        )
    return bundles


async def _verify_recorded_bundle_bytes(bundle: ExportBundle) -> bytes:
    """Read and recheck stored ZIP bytes before an authenticated delivery."""

    try:
        content = get_private_bytes(
            object_key=bundle.object_key,
            max_bytes=min(get_settings().asset_max_bytes, 50_000_000),
        )
        if len(content) != bundle.size_bytes:
            raise ExportBundleError(
                "The private export ZIP size does not match its immutable record."
            )
        if hashlib.sha256(content).hexdigest() != bundle.checksum_sha256:
            raise ExportBundleError(
                "The private export ZIP hash does not match its immutable record."
            )
        valid, errors = verify_export_bundle(content)
        if not valid:
            raise ExportBundleError("; ".join(errors))
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            manifest_value = json.loads(archive.read("export-manifest.json"))
        if (
            not isinstance(manifest_value, dict)
            or canonical_hash(manifest_value) != bundle.manifest_hash
            or canonical_hash(bundle.manifest) != bundle.manifest_hash
        ):
            raise ExportBundleError("The private export ZIP manifest does not match its record.")
        return content
    except (
        BotoCoreError,
        ClientError,
        ExportBundleError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
    ) as exc:
        raise ExportGateError(
            "The private export bundle cannot be verified for a fresh download link."
        ) from exc


def _plain_language_export_report(lineage: ExportLineage, readiness: ExportReadiness) -> str:
    """A clear, non-promissory report included inside the private ZIP."""

    release_label = f"{lineage.release.manifest.template_id} {lineage.release.manifest.version}"
    return "\n".join(
        (
            "AccessForge controlled-export record",
            "",
            f"Candidate: {lineage.candidate.id}",
            f"Reviewed template release: {release_label}",
            f"DesignSpec hash: {lineage.design_spec.spec_hash}",
            f"Deterministic validation record: {lineage.validation.report_hash}",
            f"Fresh risk recheck input hash: {readiness.risk_input_hash}",
            "",
            "This ZIP records exact private software artifacts and non-human",
            "controlled-validation context for the immutable candidate above. Its release",
            "depended on a fresh server-side recheck, an exact user acknowledgement, and",
            "reviewer-controlled evidence records.",
            "",
            "It is not professional approval, a safety certification, a fit result, a",
            "printability guarantee, a manufacturing authorization, or permission for human",
            "physical use. Any hazard, breakage, discomfort, fit issue, or near miss must",
            "be reported and blocks the",
            "affected candidate until a new review path is completed.",
        )
    )


def _bundle_lineage(
    lineage: ExportLineage, readiness: ExportReadiness, approval: ApprovalEvent
) -> dict[str, object]:
    return {
        "approval_event_id": approval.id,
        "approval_hash": approval.approval_hash,
        "artifact_manifest_hash": readiness.artifact_manifest_hash,
        "candidate_id": lineage.candidate.id,
        "design_plan_id": lineage.plan.id,
        "design_spec_hash": lineage.design_spec.spec_hash,
        "generation_batch_id": lineage.batch.id,
        "requirements_revision_id": lineage.requirements_revision.id,
        "risk_assessment_id": lineage.assessment.id,
        "risk_decision_hash": readiness.risk_decision_hash,
        "risk_input_hash": readiness.risk_input_hash,
        "template_manifest_sha256": lineage.release.manifest_sha256,
        "template_release": {
            "template_id": lineage.release.manifest.template_id,
            "version": lineage.release.manifest.version,
        },
        "validation_report_hash": lineage.validation.report_hash,
    }


def _export_object_key(
    *, project_id: str, candidate_id: str, bundle_id: str, checksum_sha256: str
) -> str:
    return (
        f"private/{project_id}/exports/{candidate_id}/{bundle_id}/"
        f"{checksum_sha256}/{EXPORT_BUNDLE_FILENAME}"
    )


def _validate_acknowledgements(acknowledgements: dict[str, object]) -> None:
    required = {
        "exact_revision_reviewed",
        "limitations_understood",
        "non_human_controlled_validation_only",
    }
    if set(acknowledgements) != required or any(
        acknowledgements.get(key) is not True for key in required
    ):
        raise ExportGateError(
            "All current controlled-export acknowledgements must be explicitly confirmed."
        )


def _required_hash(value: str | None) -> str:
    if not _is_sha256(value):
        raise ExportGateError("A current cryptographic revalidation hash is required.")
    assert isinstance(value, str)  # Narrowed after the closed SHA-256 guard above.
    return value


def _first_reason(reasons: tuple[str, ...]) -> str:
    return reasons[0] if reasons else "The controlled-export gate did not permit this candidate."


def _require_controlled_validation_reviewer(actor_role: str, settings: Settings) -> None:
    if actor_role not in settings.phase6_reviewer_role_set:
        raise ExportGateError("A configured controlled-validation reviewer role is required.")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


async def _invalidate_release_approvals(
    session: AsyncSession,
    *,
    template_manifest_sha256: str,
    actor_id: str,
    reason: str,
) -> None:
    """Invalidate release-bound approvals after any reviewer control revision.

    A user hazard remains local to its project.  Only a configured reviewer can
    affect every active acknowledgement tied to a template release.
    """

    project_ids = list(
        (
            await session.scalars(
                select(ApprovalEvent.project_id)
                .join(CandidateDesign, ApprovalEvent.candidate_id == CandidateDesign.id)
                .where(
                    ApprovalEvent.status == "active",
                    CandidateDesign.template_manifest_sha256 == template_manifest_sha256,
                )
                .distinct()
            )
        ).all()
    )
    for project_id in project_ids:
        project = await session.get(Project, project_id)
        if project is not None:
            await invalidate_active_risk_assessment(
                session,
                project=project,
                actor_id=actor_id,
                reason=reason,
            )
