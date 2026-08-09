"""Versioned deterministic risk assessment and bounded planning routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import (
    CandidateDesign,
    CandidateGenerationBatch,
    DesignPlan,
    DesignPlanProposal,
    DesignSpecRevision,
    Project,
    RiskAssessment,
    RiskFinding,
)
from accessforge.db.session import get_session
from accessforge.jobs.tasks import compile_cad_candidate
from accessforge.planning.service import (
    cancel_comparison_batch,
    cancel_plan,
    create_bounded_plan,
    queue_comparison_batch,
    record_comparison_dispatch_deferred,
    select_compared_candidate,
    select_plan_proposal,
)
from accessforge.projects.workflow import get_owned_project
from accessforge.risk.schemas import RiskContextInput
from accessforge.risk.service import (
    RiskGateError,
    current_confirmed_requirements,
    get_current_risk_assessment,
    persist_risk_assessment,
)
from accessforge.validation.service import validation_limitations

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["risk and bounded planning"])


class RiskAssessmentCreate(RiskContextInput):
    design_spec_id: str = Field(min_length=1, max_length=36)


class MatchedRiskRuleRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    tier: str
    status: str
    evidence_refs: list[str]
    explanation: str
    remediation: str | None


class RiskAssessmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    tier: str
    ruleset_version: str
    ruleset_hash: str
    input_hash: str
    decision_hash: str
    design_spec_id: str
    resulting_design_spec_id: str | None
    requirements_revision_id: str
    matched_rules: list[MatchedRiskRuleRead]
    unresolved_questions: list[str]
    allowed_actions: list[str]
    user_explanation: str
    created_at: datetime
    invalidated_at: datetime | None
    invalidated_reason: str | None


class DesignPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_assessment_id: str = Field(min_length=1, max_length=36)


class DesignPlanProposalRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    label: str
    tradeoffs: list[str]
    design_spec_id: str
    explanation: str


class ComparisonCandidateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    design_spec_id: str
    candidate_number: int
    status: str
    variant_key: str | None
    variant_label: str | None
    validation_status: str | None
    validation_limitations: list[str]
    failure_category: str | None


class CandidateComparisonBatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    design_plan_id: str
    risk_assessment_id: str
    input_hash: str
    requested_at: datetime
    cancel_requested_at: datetime | None
    completed_at: datetime | None
    candidates: list[ComparisonCandidateRead]


class DesignPlanRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    label: str
    tradeoffs: list[str]
    design_spec_id: str
    risk_assessment_id: str
    proposals: list[DesignPlanProposalRead]
    waiting_for_user_message: str | None
    required_user_action: str | None
    failure_category: str | None
    comparison_batch: CandidateComparisonBatchRead | None
    created_at: datetime
    updated_at: datetime


async def _assessment_read(session: AsyncSession, assessment: RiskAssessment) -> RiskAssessmentRead:
    findings = list(
        (
            await session.scalars(
                select(RiskFinding)
                .where(RiskFinding.risk_assessment_id == assessment.id)
                .order_by(RiskFinding.created_at.asc(), RiskFinding.id.asc())
            )
        ).all()
    )
    return RiskAssessmentRead(
        id=assessment.id,
        status=assessment.status,
        tier=assessment.tier,
        ruleset_version=assessment.ruleset_version,
        ruleset_hash=assessment.ruleset_hash,
        input_hash=assessment.input_hash,
        decision_hash=assessment.decision_hash,
        design_spec_id=assessment.design_spec_id,
        resulting_design_spec_id=assessment.resulting_design_spec_id,
        requirements_revision_id=assessment.requirements_revision_id,
        matched_rules=[
            MatchedRiskRuleRead(
                rule_id=finding.rule_id,
                tier=finding.tier,
                status=finding.status,
                evidence_refs=[value for value in finding.evidence_refs if isinstance(value, str)],
                explanation=finding.explanation,
                remediation=finding.remediation,
            )
            for finding in findings
        ],
        unresolved_questions=[
            value for value in assessment.unresolved_questions if isinstance(value, str)
        ],
        allowed_actions=[value for value in assessment.allowed_actions if isinstance(value, str)],
        user_explanation=assessment.user_explanation,
        created_at=assessment.created_at,
        invalidated_at=assessment.invalidated_at,
        invalidated_reason=assessment.invalidated_reason,
    )


async def _comparison_batch_read(
    session: AsyncSession, batch: CandidateGenerationBatch
) -> CandidateComparisonBatchRead:
    candidates = list(
        (
            await session.scalars(
                select(CandidateDesign)
                .where(CandidateDesign.generation_batch_id == batch.id)
                .order_by(CandidateDesign.candidate_number.asc())
            )
        ).all()
    )
    return CandidateComparisonBatchRead(
        id=batch.id,
        status=batch.status,
        design_plan_id=batch.design_plan_id,
        risk_assessment_id=batch.risk_assessment_id,
        input_hash=batch.input_hash,
        requested_at=batch.requested_at,
        cancel_requested_at=batch.cancel_requested_at,
        completed_at=batch.completed_at,
        candidates=[
            ComparisonCandidateRead(
                id=candidate.id,
                design_spec_id=candidate.design_spec_id,
                candidate_number=candidate.candidate_number,
                status=candidate.status,
                variant_key=candidate.variant_key,
                variant_label=candidate.variant_label,
                validation_status=candidate.validation_status,
                validation_limitations=validation_limitations(candidate.validation_report),
                failure_category=candidate.failure_category,
            )
            for candidate in candidates
        ],
    )


async def _plan_read(session: AsyncSession, plan: DesignPlan) -> DesignPlanRead:
    proposals = list(
        (
            await session.scalars(
                select(DesignPlanProposal)
                .where(DesignPlanProposal.plan_id == plan.id)
                .order_by(DesignPlanProposal.proposal_number.asc())
            )
        ).all()
    )
    source = await session.get(DesignSpecRevision, plan.source_design_spec_id)
    source_label = (
        source.template_id.replace("_", " ").title() if source is not None else "Bounded candidate"
    )
    summary_unassessed = plan.critique_summary.get("unassessed_properties")
    tradeoffs = (
        [value for value in summary_unassessed if isinstance(value, str)]
        if isinstance(summary_unassessed, list)
        else []
    )
    batch = await session.scalar(
        select(CandidateGenerationBatch)
        .where(CandidateGenerationBatch.design_plan_id == plan.id)
        .order_by(CandidateGenerationBatch.requested_at.desc())
    )
    return DesignPlanRead(
        id=plan.id,
        status=plan.status,
        label=f"{source_label} comparison plan {plan.plan_number}",
        tradeoffs=tradeoffs,
        design_spec_id=plan.source_design_spec_id,
        risk_assessment_id=plan.risk_assessment_id,
        proposals=[
            DesignPlanProposalRead(
                id=proposal.id,
                status=proposal.status,
                label=proposal.label,
                tradeoffs=[value for value in proposal.tradeoffs if isinstance(value, str)],
                design_spec_id=proposal.design_spec_id,
                explanation=proposal.rationale,
            )
            for proposal in proposals
        ],
        waiting_for_user_message=plan.user_checkpoint
        if plan.status == "waiting_for_user"
        else None,
        required_user_action=(
            "Choose one starting point or explicitly queue the complete private comparison."
            if plan.status == "waiting_for_user"
            else None
        ),
        failure_category=None,
        comparison_batch=await _comparison_batch_read(session, batch)
        if batch is not None
        else None,
        created_at=plan.created_at,
        updated_at=plan.cancelled_at or plan.created_at,
    )


@router.get("/risk", response_model=RiskAssessmentRead)
async def get_risk(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> RiskAssessmentRead:
    project = await get_owned_project(session, principal, project_id)
    assessment = await get_current_risk_assessment(session, project)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No current risk assessment."
        )
    return await _assessment_read(session, assessment)


@router.post("/risk:assess", response_model=RiskAssessmentRead, status_code=status.HTTP_201_CREATED)
async def assess_risk(
    project_id: str,
    payload: RiskAssessmentCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> RiskAssessmentRead:
    project = await get_owned_project(session, principal, project_id)
    if project.status not in {"risk_review", "ready_for_generation"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Confirm requirements and return to deterministic risk review before "
                "assessing this project."
            ),
        )
    requirements_revision = await current_confirmed_requirements(session, project)
    source_spec = await session.scalar(
        select(DesignSpecRevision).where(
            DesignSpecRevision.id == payload.design_spec_id,
            DesignSpecRevision.project_id == project.id,
        )
    )
    if source_spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DesignSpec not found.")
    if source_spec.requirements_revision_id != requirements_revision.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The DesignSpec is based on an older requirements revision and must be recreated."
            ),
        )
    try:
        assessment, _ = await persist_risk_assessment(
            session,
            project=project,
            requirements_revision=requirements_revision,
            source_spec=source_spec,
            context=RiskContextInput.model_validate(payload.model_dump(exclude={"design_spec_id"})),
            actor_id=principal.subject,
        )
    except RiskGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _assessment_read(session, assessment)


@router.get("/design-plans", response_model=list[DesignPlanRead])
async def list_design_plans(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[DesignPlanRead]:
    project = await get_owned_project(session, principal, project_id)
    plans = list(
        (
            await session.scalars(
                select(DesignPlan)
                .where(DesignPlan.project_id == project.id)
                .order_by(DesignPlan.plan_number.desc())
            )
        ).all()
    )
    return [await _plan_read(session, plan) for plan in plans]


@router.post("/design-plans", response_model=DesignPlanRead, status_code=status.HTTP_201_CREATED)
async def create_design_plan(
    project_id: str,
    payload: DesignPlanCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> DesignPlanRead:
    project = await get_owned_project(session, principal, project_id)
    assessment = await get_current_risk_assessment(session, project)
    if assessment is None or assessment.id != payload.risk_assessment_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate planning requires the current server-owned risk assessment.",
        )
    try:
        plan = await create_bounded_plan(
            session, project=project, assessment=assessment, actor_id=principal.subject
        )
    except RiskGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _plan_read(session, plan)


async def _owned_plan(session: AsyncSession, project: Project, plan_id: str) -> DesignPlan:
    plan = await session.scalar(
        select(DesignPlan).where(DesignPlan.id == plan_id, DesignPlan.project_id == project.id)
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design plan not found.")
    return plan


@router.post(
    "/design-plans/{plan_id}/proposals/{proposal_id}:select", response_model=DesignPlanRead
)
async def select_design_plan_proposal(
    project_id: str,
    plan_id: str,
    proposal_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> DesignPlanRead:
    project = await get_owned_project(session, principal, project_id)
    plan = await _owned_plan(session, project, plan_id)
    proposal = await session.scalar(
        select(DesignPlanProposal).where(
            DesignPlanProposal.id == proposal_id, DesignPlanProposal.plan_id == plan.id
        )
    )
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Design plan proposal not found."
        )
    try:
        updated = await select_plan_proposal(
            session, project=project, plan=plan, proposal=proposal, actor_id=principal.subject
        )
    except RiskGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _plan_read(session, updated)


@router.post("/design-plans/{plan_id}:cancel", response_model=DesignPlanRead)
async def cancel_design_plan(
    project_id: str,
    plan_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> DesignPlanRead:
    project = await get_owned_project(session, principal, project_id)
    plan = await _owned_plan(session, project, plan_id)
    try:
        updated = await cancel_plan(session, project=project, plan=plan, actor_id=principal.subject)
    except RiskGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _plan_read(session, updated)


@router.post(
    "/design-plans/{plan_id}:generate-comparison",
    response_model=CandidateComparisonBatchRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_comparison(
    project_id: str,
    plan_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> CandidateComparisonBatchRead:
    project = await get_owned_project(session, principal, project_id)
    plan = await _owned_plan(session, project, plan_id)
    assessment = await get_current_risk_assessment(session, project)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A current deterministic R1 decision is required before a comparison batch.",
        )
    try:
        queued = await queue_comparison_batch(
            session,
            project=project,
            assessment=assessment,
            plan=plan,
            actor_id=principal.subject,
            idempotency_key=idempotency_key,
        )
    except RiskGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    pending_candidates = [
        candidate for candidate in queued.candidates if candidate.status == "queued"
    ]
    if pending_candidates:
        try:
            for candidate in pending_candidates:
                compile_cad_candidate.delay(candidate.id)
        except Exception as exc:
            await record_comparison_dispatch_deferred(
                session,
                project=project,
                batch=queued.batch,
                actor_id="system:cad-api",
                error=exc,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "The private comparison is durably queued and will be retried by the "
                    "background dispatcher. No export or approval occurred."
                ),
            ) from exc
    return await _comparison_batch_read(session, queued.batch)


@router.post(
    "/design-plans/{plan_id}/comparison:cancel", response_model=CandidateComparisonBatchRead
)
async def cancel_comparison(
    project_id: str,
    plan_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> CandidateComparisonBatchRead:
    project = await get_owned_project(session, principal, project_id)
    plan = await _owned_plan(session, project, plan_id)
    batch = await session.scalar(
        select(CandidateGenerationBatch)
        .where(CandidateGenerationBatch.design_plan_id == plan.id)
        .order_by(CandidateGenerationBatch.requested_at.desc())
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comparison batch not found."
        )
    try:
        updated = await cancel_comparison_batch(
            session,
            project=project,
            plan=plan,
            batch=batch,
            actor_id=principal.subject,
        )
    except RiskGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _comparison_batch_read(session, updated)


@router.post(
    "/design-plans/{plan_id}/comparison/candidates/{candidate_id}:select",
    response_model=DesignPlanRead,
)
async def select_comparison_candidate(
    project_id: str,
    plan_id: str,
    candidate_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> DesignPlanRead:
    project = await get_owned_project(session, principal, project_id)
    plan = await _owned_plan(session, project, plan_id)
    batch = await session.scalar(
        select(CandidateGenerationBatch)
        .where(CandidateGenerationBatch.design_plan_id == plan.id)
        .order_by(CandidateGenerationBatch.requested_at.desc())
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comparison batch not found."
        )
    candidate = await session.scalar(
        select(CandidateDesign).where(
            CandidateDesign.id == candidate_id,
            CandidateDesign.project_id == project.id,
            CandidateDesign.generation_batch_id == batch.id,
        )
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comparison candidate not found."
        )
    try:
        updated = await select_compared_candidate(
            session,
            project=project,
            plan=plan,
            batch=batch,
            candidate=candidate,
            actor_id=principal.subject,
        )
    except RiskGateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _plan_read(session, updated)
