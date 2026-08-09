"""Persistence, lineage, invalidation, and server-side risk gates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.cad.registry import TemplateRegistryError, validate_design_spec
from accessforge.cad.schemas import DesignSpec, FieldProvenance, canonical_hash
from accessforge.core.config import get_settings
from accessforge.db.models import (
    ApprovalEvent,
    AuditEvent,
    CandidateDesign,
    CandidateValidationRun,
    DesignPlan,
    DesignPlanProposal,
    DesignSpecRevision,
    ExportBundle,
    Measurement,
    Observation,
    Project,
    Requirement,
    RequirementRevision,
    RiskAssessment,
    RiskAssessmentContext,
    RiskFinding,
)
from accessforge.projects.workflow import transition_project
from accessforge.risk.engine import evaluate_risk
from accessforge.risk.private_context import (
    RISK_CONTEXT_ENVELOPE_VERSION,
    RiskContextSealError,
    context_hash,
    seal_risk_context,
)
from accessforge.risk.schemas import RiskContextInput, RiskDecision
from accessforge.validation.service import validation_allows_phase6_export


class RiskGateError(ValueError):
    """A required immutable deterministic gate is missing, stale, or blocked."""


@dataclass(frozen=True)
class RiskEvaluationBundle:
    decision: RiskDecision
    input_snapshot: dict[str, object]
    input_hash: str


async def current_confirmed_requirements(
    session: AsyncSession, project: Project
) -> RequirementRevision:
    revision_id = project.active_requirement_revision_id
    if revision_id is None:
        raise RiskGateError("Confirm a requirements revision before deterministic risk assessment.")
    revision = await session.scalar(
        select(RequirementRevision).where(
            RequirementRevision.id == revision_id,
            RequirementRevision.project_id == project.id,
            RequirementRevision.status == "confirmed",
        )
    )
    if revision is None:
        raise RiskGateError(
            "The active requirements revision is not a confirmed immutable revision."
        )
    return revision


async def evaluate_project_risk(
    session: AsyncSession,
    *,
    project: Project,
    requirements_revision: RequirementRevision,
    source_spec: DesignSpecRevision,
    context: RiskContextInput,
) -> RiskEvaluationBundle:
    """Build a hashable snapshot without copying raw observations into audit rows."""

    try:
        source_document = DesignSpec.model_validate(source_spec.canonical_spec)
        validate_design_spec(source_document)
    except (TemplateRegistryError, ValueError) as exc:
        raise RiskGateError(
            "The selected immutable DesignSpec is not a current reviewed input."
        ) from exc
    measurements = list(
        (
            await session.scalars(
                select(Measurement)
                .where(Measurement.project_id == project.id)
                .order_by(Measurement.created_at.asc())
            )
        ).all()
    )
    observations = list(
        (
            await session.scalars(
                select(Observation)
                .where(Observation.project_id == project.id, Observation.input_mode == "text")
                .order_by(Observation.created_at.asc())
            )
        ).all()
    )
    requirements = list(
        (
            await session.scalars(
                select(Requirement)
                .where(Requirement.revision_id == requirements_revision.id)
                .order_by(Requirement.created_at.asc())
            )
        ).all()
    )
    text_sources = _project_text_sources(project)
    for observation in observations:
        text_sources[f"observation:{observation.id}"] = observation.text
    for requirement in requirements:
        if requirement.value_text:
            text_sources[f"requirement:{requirement.id}"] = requirement.value_text
        if requirement.explanation:
            text_sources[f"requirement-explanation:{requirement.id}"] = requirement.explanation
    source_refs = {
        "risk:context",
        "risk:intended-use",
        "risk:requirements",
        "risk:design-spec",
        "risk:template",
        "project:scope_status",
        "project:safety_system",
        *text_sources.keys(),
    }
    for requirement in requirements:
        source_refs.update(item for item in requirement.source_refs if isinstance(item, str))
    source_refs.update(f"measurement:{measurement.id}" for measurement in measurements)
    signals = _records(requirements_revision.risk_signals)
    if requirements_revision.unknowns:
        signals.append({"level": "needs_confirmation", "source_refs": ["risk:requirements"]})
    decision = evaluate_risk(
        context=context,
        project_facts={
            "scope_status": project.scope_status,
            "safety_system": project.safety_system,
            "text_sources": text_sources,
        },
        requirement_signals=signals,
        source_refs=source_refs,
        template_id=source_document.template_id,
        template_version=source_document.template_version,
        template_manifest_sha256=source_document.template_manifest_sha256,
        has_confirmed_requirements=requirements_revision.status == "confirmed",
        spec_unresolved_assumptions=source_document.unresolved_assumptions,
    )
    context_snapshot = context.model_dump(mode="json")
    intended_use = context_snapshot.pop("intended_use")
    if not isinstance(intended_use, str):  # pragma: no cover - closed input contract guard
        raise RiskGateError("The deterministic risk context is malformed.")
    context_snapshot["intended_use_hash"] = _content_hash(intended_use)
    snapshot: dict[str, object] = {
        "risk_context": context_snapshot,
        "project": {
            "id": project.id,
            "version": project.version,
            "scope_status": project.scope_status,
            "safety_system": project.safety_system,
            "text_source_hashes": {
                source_ref: _content_hash(value)
                for source_ref, value in sorted(text_sources.items())
            },
        },
        "requirements_revision": {
            "id": requirements_revision.id,
            "content_hash": requirements_revision.content_hash,
            "unknown_count": len(requirements_revision.unknowns or []),
            "risk_signal_count": len(requirements_revision.risk_signals or []),
        },
        "measurements": [
            {
                "id": measurement.id,
                "version": measurement.version,
                "kind": measurement.kind,
                "canonical_value_mm": measurement.canonical_value_mm,
                "canonical_tolerance_mm": measurement.canonical_tolerance_mm,
                "method": measurement.method,
                "confirmed": measurement.confirmed,
                "unknown": measurement.unknown,
            }
            for measurement in measurements
        ],
        "design_spec": {
            "id": source_spec.id,
            "spec_hash": source_spec.spec_hash,
            "template_id": source_document.template_id,
            "template_version": source_document.template_version,
            "template_manifest_sha256": source_document.template_manifest_sha256,
            "manufacturing": source_document.manufacturing.model_dump(mode="json"),
        },
    }
    return RiskEvaluationBundle(
        decision=decision,
        input_snapshot=snapshot,
        input_hash=canonical_hash(snapshot),
    )


async def persist_risk_assessment(
    session: AsyncSession,
    *,
    project: Project,
    requirements_revision: RequirementRevision,
    source_spec: DesignSpecRevision,
    context: RiskContextInput,
    actor_id: str,
) -> tuple[RiskAssessment, DesignSpecRevision]:
    """Persist an assessment and a newly risk-bound immutable DesignSpec revision."""

    bundle = await evaluate_project_risk(
        session,
        project=project,
        requirements_revision=requirements_revision,
        source_spec=source_spec,
        context=context,
    )
    previous_id = project.active_risk_assessment_id
    if previous_id:
        await invalidate_active_risk_assessment(
            session,
            project=project,
            actor_id=actor_id,
            reason="A newer deterministic risk assessment superseded the prior decision.",
            reset_project_state=False,
        )
    assessment = RiskAssessment(
        project_id=project.id,
        requirements_revision_id=requirements_revision.id,
        design_spec_id=source_spec.id,
        previous_assessment_id=previous_id,
        assessment_number=await _next_assessment_number(session, project.id),
        assessment_scope="pre_generation",
        project_version=project.version,
        ruleset_version=bundle.decision.ruleset_version,
        ruleset_hash=bundle.decision.ruleset_hash,
        input_snapshot=bundle.input_snapshot,
        input_hash=bundle.input_hash,
        tier=bundle.decision.tier,
        status="current",
        allowed_actions=list(bundle.decision.allowed_actions),
        unresolved_questions=list(bundle.decision.unresolved_questions),
        user_explanation=bundle.decision.user_explanation,
        decision_hash="0" * 64,
        created_by=actor_id,
    )
    session.add(assessment)
    await session.flush()
    settings = get_settings()
    if settings.risk_context_encryption_key:
        try:
            sealed_context = seal_risk_context(
                context,
                key=settings.risk_context_encryption_key,
                project_id=project.id,
                assessment_id=assessment.id,
            )
        except RiskContextSealError as exc:
            raise RiskGateError(
                "The private risk context could not be retained for later export revalidation."
            ) from exc
        session.add(
            RiskAssessmentContext(
                risk_assessment_id=assessment.id,
                context_hash=context_hash(context),
                envelope_version=RISK_CONTEXT_ENVELOPE_VERSION,
                encrypted_context=sealed_context,
            )
        )
    resulting_spec = await _create_risk_bound_spec(
        session,
        project=project,
        requirements_revision=requirements_revision,
        source_spec=source_spec,
        decision=bundle.decision,
        assessment_id=assessment.id,
        actor_id=actor_id,
    )
    assessment.resulting_design_spec_id = resulting_spec.id
    assessment.decision_hash = canonical_hash(
        {
            "input_hash": assessment.input_hash,
            "tier": assessment.tier,
            "ruleset_version": assessment.ruleset_version,
            "ruleset_hash": assessment.ruleset_hash,
            "matched_findings": [
                item.model_dump(mode="json") for item in bundle.decision.matched_findings
            ],
            "unresolved_questions": assessment.unresolved_questions,
            "allowed_actions": assessment.allowed_actions,
            "resulting_design_spec_id": resulting_spec.id,
            "resulting_spec_hash": resulting_spec.spec_hash,
        }
    )
    for finding in bundle.decision.matched_findings:
        session.add(
            RiskFinding(
                risk_assessment_id=assessment.id,
                rule_id=finding.rule_id,
                rule_version=finding.rule_version,
                tier=finding.tier,
                status=finding.status,
                evidence_refs=[item.source_ref for item in finding.evidence],
                explanation=finding.explanation,
                remediation=finding.remediation,
            )
        )
    project.active_risk_assessment_id = assessment.id
    if assessment.tier != "R1" and project.status != "risk_review":
        transition_project(
            session,
            project,
            target="risk_review",
            actor_id=actor_id,
            reason="The replacement deterministic risk decision no longer permits generation.",
            details={"risk_assessment_id": assessment.id, "tier": assessment.tier},
        )
    if assessment.tier == "R1" and project.status == "risk_review":
        transition_project(
            session,
            project,
            target="ready_for_generation",
            actor_id=actor_id,
            reason=(
                "A current deterministic R1 decision permits bounded private candidate generation."
            ),
            details={"risk_assessment_id": assessment.id, "design_spec_id": resulting_spec.id},
        )
    elif assessment.tier == "R3" and project.status == "risk_review":
        transition_project(
            session,
            project,
            target="blocked_out_of_scope",
            actor_id=actor_id,
            reason="A deterministic R3 decision prohibits automatic geometry in this MVP.",
            details={"risk_assessment_id": assessment.id},
        )
    elif assessment.tier == "R0" and project.status == "risk_review":
        transition_project(
            session,
            project,
            target="needs_more_information",
            actor_id=actor_id,
            reason="The deterministic risk assessment lacks facts required for geometry.",
            details={"risk_assessment_id": assessment.id},
        )
    assessment.project_version = project.version
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="risk.assessed",
            reason=(
                "A versioned deterministic risk assessment created a new immutable "
                "DesignSpec revision."
            ),
            details={
                "risk_assessment_id": assessment.id,
                "tier": assessment.tier,
                "source_design_spec_id": source_spec.id,
                "resulting_design_spec_id": resulting_spec.id,
                "ruleset_version": assessment.ruleset_version,
            },
        )
    )
    await session.commit()
    await session.refresh(assessment)
    await session.refresh(resulting_spec)
    return assessment, resulting_spec


async def invalidate_active_risk_assessment(
    session: AsyncSession,
    *,
    project: Project,
    actor_id: str,
    reason: str,
    reset_project_state: bool = True,
) -> None:
    """Invalidate a pointer and immutable row; never edit the historical decision."""

    active_id = project.active_risk_assessment_id
    if active_id:
        assessment = await session.scalar(
            select(RiskAssessment).where(
                RiskAssessment.id == active_id, RiskAssessment.project_id == project.id
            )
        )
        if assessment is not None and assessment.status == "current":
            assessment.status = "invalidated"
            assessment.invalidated_at = datetime.now(UTC)
            assessment.invalidated_reason = reason
        project.active_risk_assessment_id = None
    invalidated_approvals = await invalidate_project_export_authorizations(
        session,
        project=project,
        actor_id=actor_id,
        reason=reason,
    )
    if reset_project_state and project.status in {
        "ready_for_generation",
        "planning",
        "waiting_for_user",
        "generating",
        "candidates_ready",
        "user_review",
        "blocked_out_of_scope",
        "needs_more_information",
        "approved",
        "export_ready",
    }:
        transition_project(
            session,
            project,
            target="risk_review",
            actor_id=actor_id,
            reason=(
                "A risk-relevant project input changed, so the prior decision is no longer current."
            ),
            details={"reason": reason, "risk_assessment_id": active_id},
        )
    if active_id or invalidated_approvals:
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id=actor_id,
                event_type="risk.invalidated",
                reason=reason,
                details={
                    "risk_assessment_id": active_id,
                    "invalidated_approval_count": invalidated_approvals,
                },
            )
        )


async def invalidate_project_export_authorizations(
    session: AsyncSession,
    *,
    project: Project,
    actor_id: str,
    reason: str,
) -> int:
    """Revoke active export acknowledgements without deleting immutable history.

    A relevant project revision invalidates an old approval even if the risk
    pointer was already cleared by an earlier request.  Any private ZIP remains
    retained for audit/deletion purposes but is no longer downloadable.
    """

    approvals = list(
        (
            await session.scalars(
                select(ApprovalEvent).where(
                    ApprovalEvent.project_id == project.id,
                    ApprovalEvent.status == "active",
                )
            )
        ).all()
    )
    if not approvals:
        return 0
    now = datetime.now(UTC)
    approval_ids = [approval.id for approval in approvals]
    for approval in approvals:
        approval.status = "invalidated"
        approval.invalidated_at = now
        approval.invalidated_reason = reason
    bundles = list(
        (
            await session.scalars(
                select(ExportBundle).where(
                    ExportBundle.project_id == project.id,
                    ExportBundle.approval_event_id.in_(approval_ids),
                    ExportBundle.status == "ready",
                )
            )
        ).all()
    )
    for bundle in bundles:
        bundle.status = "revoked"
        bundle.revoked_at = now
        bundle.revoked_reason = reason
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="export.approvals_invalidated",
            reason="A relevant revision invalidated exact export acknowledgements.",
            details={
                "approval_count": len(approvals),
                "bundle_count": len(bundles),
                "reason": reason,
            },
        )
    )
    return len(approvals)


async def get_current_risk_assessment(
    session: AsyncSession, project: Project
) -> RiskAssessment | None:
    if not project.active_risk_assessment_id:
        return None
    return cast(
        RiskAssessment | None,
        await session.scalar(
            select(RiskAssessment).where(
                RiskAssessment.id == project.active_risk_assessment_id,
                RiskAssessment.project_id == project.id,
                RiskAssessment.status == "current",
            )
        ),
    )


async def assert_generation_allowed(
    session: AsyncSession,
    *,
    project: Project,
    design_spec: DesignSpecRevision,
    expected_assessment_id: str | None = None,
    authorized_plan_id: str | None = None,
) -> RiskAssessment:
    """Fail closed for API and worker calls, including queue-time stale inputs."""

    if project.scope_status != "supported":
        raise RiskGateError("The project is not within the supported deterministic MVP scope.")
    assessment = await get_current_risk_assessment(session, project)
    if assessment is None or assessment.tier != "R1":
        raise RiskGateError(
            "A current deterministic R1 risk decision is required before generation."
        )
    if "generate_candidate" not in assessment.allowed_actions:
        raise RiskGateError(
            "The current deterministic risk decision does not permit private candidates."
        )
    if expected_assessment_id is not None and assessment.id != expected_assessment_id:
        raise RiskGateError("The queued candidate is not bound to the current risk assessment.")
    if assessment.requirements_revision_id != project.active_requirement_revision_id:
        raise RiskGateError(
            "The risk assessment no longer matches the active requirements revision."
        )
    if (
        design_spec.project_id != project.id
        or design_spec.requirements_revision_id != assessment.requirements_revision_id
        or design_spec.risk_assessment_id != assessment.id
    ):
        raise RiskGateError(
            "The immutable DesignSpec is not bound to the current project, requirements, and "
            "deterministic risk decision."
        )
    proposals = list(
        (
            await session.scalars(
                select(DesignPlanProposal)
                .join(DesignPlan, DesignPlanProposal.plan_id == DesignPlan.id)
                .where(
                    DesignPlanProposal.design_spec_id == design_spec.id,
                    DesignPlan.risk_assessment_id == assessment.id,
                )
            )
        ).all()
    )
    if authorized_plan_id is not None:
        plan = await session.scalar(
            select(DesignPlan).where(
                DesignPlan.id == authorized_plan_id,
                DesignPlan.project_id == project.id,
                DesignPlan.risk_assessment_id == assessment.id,
                DesignPlan.status.in_({"waiting_for_user", "comparison_queued"}),
            )
        )
        if plan is None:
            raise RiskGateError("The comparison plan is no longer authorized for generation.")
        authorized = any(
            proposal.plan_id == authorized_plan_id
            and proposal.status in {"proposed", "comparison_queued"}
            for proposal in proposals
        )
        if not authorized:
            raise RiskGateError(
                "The DesignSpec is not an authorized member of the requested comparison plan."
            )
    elif proposals:
        selected = await session.scalar(
            select(DesignPlanProposal)
            .join(DesignPlan, DesignPlanProposal.plan_id == DesignPlan.id)
            .where(
                DesignPlanProposal.design_spec_id == design_spec.id,
                DesignPlan.risk_assessment_id == assessment.id,
                DesignPlanProposal.status == "selected",
                DesignPlan.status == "confirmed",
            )
        )
        if selected is None:
            raise RiskGateError(
                "A plan-created DesignSpec must be selected or queued through its comparison gate."
            )
    try:
        spec = DesignSpec.model_validate(design_spec.canonical_spec)
        validate_design_spec(spec)
    except (TemplateRegistryError, ValueError) as exc:
        raise RiskGateError(
            "The immutable DesignSpec no longer resolves to its reviewed release."
        ) from exc
    if (
        spec.risk_tier != "R1"
        or spec.risk_rule_set_version != assessment.ruleset_version
        or spec.unresolved_assumptions
    ):
        raise RiskGateError(
            "The DesignSpec is not a complete R1 input for the current risk decision."
        )
    return assessment


async def phase6_export_preflight(
    session: AsyncSession, *, project: Project, candidate: CandidateDesign
) -> tuple[bool, list[str]]:
    """Reusable pre-export gate; Phase 5 intentionally cannot approve or export."""

    reasons: list[str] = []
    try:
        await assert_generation_allowed(
            session,
            project=project,
            design_spec=await _candidate_spec(session, candidate),
            expected_assessment_id=candidate.risk_assessment_id,
        )
    except RiskGateError as exc:
        reasons.append(str(exc))
    validation = await session.scalar(
        select(CandidateValidationRun)
        .where(CandidateValidationRun.candidate_id == candidate.id)
        .order_by(CandidateValidationRun.created_at.desc())
    )
    if validation is None:
        reasons.append("No immutable deterministic validation run is recorded for this candidate.")
    else:
        _, validation_reasons = validation_allows_phase6_export(validation.report)
        reasons.extend(validation_reasons)
    return False, list(dict.fromkeys(reasons))


async def _candidate_spec(session: AsyncSession, candidate: CandidateDesign) -> DesignSpecRevision:
    specification = await session.get(DesignSpecRevision, candidate.design_spec_id)
    if specification is None:
        raise RiskGateError("The candidate's immutable DesignSpec is missing.")
    return specification


async def _create_risk_bound_spec(
    session: AsyncSession,
    *,
    project: Project,
    requirements_revision: RequirementRevision,
    source_spec: DesignSpecRevision,
    decision: RiskDecision,
    assessment_id: str,
    actor_id: str,
) -> DesignSpecRevision:
    source = DesignSpec.model_validate(source_spec.canonical_spec)
    unresolved = tuple(
        dict.fromkeys((*source.unresolved_assumptions, *decision.unresolved_questions))
    )[:30]
    provenance = dict(source.field_provenance)
    decision_source = f"risk-assessment:{assessment_id}"
    provenance["risk_tier"] = FieldProvenance(
        creator_type="rule",
        source_ref=decision_source,
        rationale="A server-owned deterministic risk engine assigned this immutable tier.",
    )
    provenance["risk_rule_set_version"] = FieldProvenance(
        creator_type="rule",
        source_ref=decision_source,
        rationale="The immutable decision records the exact evaluated risk ruleset version.",
    )
    provenance["unresolved_assumptions"] = FieldProvenance(
        creator_type="rule",
        source_ref=decision_source,
        rationale="The risk decision preserves unresolved risk questions instead of hiding them.",
    )
    document = source.model_copy(
        update={
            "risk_tier": decision.tier,
            "risk_rule_set_version": decision.ruleset_version,
            "unresolved_assumptions": unresolved,
            "field_provenance": provenance,
        }
    )
    validate_design_spec(document)
    revision = DesignSpecRevision(
        project_id=project.id,
        requirements_revision_id=requirements_revision.id,
        parent_design_spec_id=source_spec.id,
        risk_assessment_id=assessment_id,
        revision_number=await _next_design_spec_number(session, project.id),
        schema_version=document.schema_version,
        template_id=document.template_id,
        template_version=document.template_version,
        template_manifest_sha256=document.template_manifest_sha256,
        canonical_spec=document.canonical_payload(),
        spec_hash=document.content_hash,
        generation_seed=document.generation_seed,
        created_by=actor_id,
    )
    session.add(revision)
    await session.flush()
    return revision


async def _next_assessment_number(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        select(func.max(RiskAssessment.assessment_number)).where(
            RiskAssessment.project_id == project_id
        )
    )
    return int(value or 0) + 1


async def _next_design_spec_number(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        select(func.max(DesignSpecRevision.revision_number)).where(
            DesignSpecRevision.project_id == project_id
        )
    )
    return int(value or 0) + 1


def _project_text_sources(project: Project) -> dict[str, str]:
    values = {
        "project:goal": project.goal,
        "project:description": project.description,
        "project:object_description": project.object_description,
        "project:action_description": project.action_description,
        "project:environment": project.environment,
        "project:load_context": project.load_context,
        "project:age_context": project.age_context,
    }
    return {
        source_ref: value
        for source_ref, value in values.items()
        if isinstance(value, str) and value
    }


def _records(values: object) -> list[dict[str, object]]:
    return (
        [dict(item) for item in values if isinstance(item, dict)]
        if isinstance(values, list)
        else []
    )


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
