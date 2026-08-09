"""Persistence for bounded Phase 5 plan checkpoints and user selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.ai.prompt_registry import get_prompt
from accessforge.cad.registry import validate_design_spec
from accessforge.cad.schemas import DesignSpec, canonical_hash
from accessforge.db.models import (
    AgentRun,
    AgentStep,
    AuditEvent,
    CadJob,
    CandidateDesign,
    CandidateGenerationBatch,
    DesignPlan,
    DesignPlanProposal,
    DesignSpecRevision,
    Project,
    RiskAssessment,
)
from accessforge.db.results import affected_row_count
from accessforge.planning.engine import (
    PlannedVariant,
    critic_summary,
    plan_variants,
    template_match,
)
from accessforge.projects.workflow import transition_project
from accessforge.risk.service import RiskGateError, assert_generation_allowed

# Phase 5 does not delegate authorization to a provider.  These limits still
# describe the durable contract for this bounded workflow and prevent a future
# provider-backed implementation from silently widening its execution budget.
MAX_BOUNDED_MODEL_TURNS = 8
MAX_BOUNDED_TOOL_CALLS = 12
BOUNDED_PLAN_TOOL_ALLOWLIST = frozenset(
    {
        "search_reviewed_templates",
        "get_template_contract",
        "pause_for_user_confirmation",
    }
)
BOUNDED_PLAN_TOOL_CALLS = (
    "search_reviewed_templates",
    "get_template_contract",
    "pause_for_user_confirmation",
)


@dataclass(frozen=True)
class QueuedComparison:
    """A durable, idempotent batch and its private child candidates."""

    batch: CandidateGenerationBatch
    candidates: tuple[CandidateDesign, ...]
    reused: bool


async def _lock_plan(session: AsyncSession, *, project_id: str, plan_id: str) -> DesignPlan | None:
    """Serialize irreversible user checkpoints for one immutable plan."""

    return cast(
        DesignPlan | None,
        await session.scalar(
            select(DesignPlan)
            .where(DesignPlan.id == plan_id, DesignPlan.project_id == project_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )


async def create_bounded_plan(
    session: AsyncSession,
    *,
    project: Project,
    assessment: RiskAssessment,
    actor_id: str,
) -> DesignPlan:
    """Create at most three server-validated variants and pause for user selection."""

    if project.status != "ready_for_generation":
        raise RiskGateError("Candidate planning requires a project ready for bounded generation.")
    if assessment.status != "current" or assessment.tier != "R1":
        raise RiskGateError("Candidate planning requires a current deterministic R1 decision.")
    if "create_design_plan" not in assessment.allowed_actions:
        raise RiskGateError(
            "The current deterministic risk decision does not permit candidate planning."
        )
    if assessment.resulting_design_spec_id is None:
        raise RiskGateError("The current risk decision has no immutable risk-bound DesignSpec.")
    source_spec = await session.scalar(
        select(DesignSpecRevision).where(
            DesignSpecRevision.id == assessment.resulting_design_spec_id,
            DesignSpecRevision.project_id == project.id,
        )
    )
    if source_spec is None:
        raise RiskGateError("The current risk-bound DesignSpec is unavailable.")
    source_document = DesignSpec.model_validate(source_spec.canonical_spec)
    validate_design_spec(source_document)
    if len(BOUNDED_PLAN_TOOL_CALLS) > MAX_BOUNDED_TOOL_CALLS or any(
        tool not in BOUNDED_PLAN_TOOL_ALLOWLIST for tool in BOUNDED_PLAN_TOOL_CALLS
    ):
        raise RiskGateError("The bounded planning tool contract is invalid.")
    variants = plan_variants(source_document)
    if len(variants) < 2:
        raise RiskGateError(
            "This template does not permit two distinct bounded variants for the current "
            "parameters."
        )
    plan_input = {
        "risk_assessment_id": assessment.id,
        "decision_hash": assessment.decision_hash,
        "source_design_spec_id": source_spec.id,
        "source_spec_hash": source_spec.spec_hash,
        "variant_hashes": [variant.design_spec.content_hash for variant in variants],
    }
    input_hash = canonical_hash(plan_input)
    planner_prompt = get_prompt("design_planner")
    run = AgentRun(
        project_id=project.id,
        provider_config_id=None,
        workflow_type="bounded_design_plan",
        provider_type="deterministic",
        model_identifier=None,
        status="succeeded",
        prompt_id=f"{planner_prompt.identifier}:{planner_prompt.version}",
        prompt_hash=planner_prompt.content_hash,
        input_hash=input_hash,
        output_hash=canonical_hash([variant.design_spec.content_hash for variant in variants]),
        input_tokens=0,
        output_tokens=0,
        estimated_cost_usd=0.0,
        latency_ms=0,
        result_rationale=(
            "A bounded deterministic planner created reviewed-template parameter comparisons only "
            f"(0/{MAX_BOUNDED_MODEL_TURNS} model turns; "
            f"{len(BOUNDED_PLAN_TOOL_CALLS)}/{MAX_BOUNDED_TOOL_CALLS} typed tool calls; "
            "no retries, provider cost, or external execution)."
        ),
    )
    session.add(run)
    await session.flush()
    matches = template_match(source_document)
    critique = critic_summary(variants)
    session.add_all(
        (
            AgentStep(
                agent_run_id=run.id,
                step_number=1,
                name="template_matcher",
                status="completed",
                tool_name="search_reviewed_templates",
                input_hash=canonical_hash({"source_spec_hash": source_spec.spec_hash}),
                output_hash=canonical_hash(matches),
                latency_ms=0,
            ),
            AgentStep(
                agent_run_id=run.id,
                step_number=2,
                name="design_planner",
                status="completed",
                tool_name="get_template_contract",
                input_hash=input_hash,
                output_hash=canonical_hash(
                    [variant.design_spec.content_hash for variant in variants]
                ),
                latency_ms=0,
            ),
            AgentStep(
                agent_run_id=run.id,
                step_number=3,
                name="design_critic",
                status="completed",
                tool_name="pause_for_user_confirmation",
                input_hash=canonical_hash(
                    [variant.design_spec.content_hash for variant in variants]
                ),
                output_hash=canonical_hash(critique),
                latency_ms=0,
            ),
        )
    )
    transition_project(
        session,
        project,
        target="planning",
        actor_id=actor_id,
        reason="A bounded reviewed-template plan is being prepared for a user checkpoint.",
        details={"risk_assessment_id": assessment.id},
    )
    plan = DesignPlan(
        project_id=project.id,
        risk_assessment_id=assessment.id,
        source_design_spec_id=source_spec.id,
        agent_run_id=run.id,
        plan_number=await _next_plan_number(session, project.id),
        status="waiting_for_user",
        input_hash=input_hash,
        template_matches=matches,
        critique_summary=critique,
        user_checkpoint=(
            "Review the bounded parameter tradeoffs and explicitly choose either one starting "
            "point or a private software-only comparison set. Neither action approves, exports, "
            "manufactures, or authorizes physical use."
        ),
        created_by=actor_id,
    )
    session.add(plan)
    await session.flush()
    for number, variant in enumerate(variants, start=1):
        specification_id = (
            source_spec.id
            if variant.uses_source_spec
            else await _persist_variant_spec(
                session,
                project=project,
                source_spec=source_spec,
                assessment=assessment,
                variant=variant,
                actor_id=actor_id,
            )
        )
        session.add(
            DesignPlanProposal(
                plan_id=plan.id,
                design_spec_id=specification_id,
                proposal_number=number,
                variant_key=variant.key,
                label=variant.label,
                rationale=variant.rationale,
                tradeoffs=list(variant.tradeoffs),
                critique={
                    "role": "design_critic",
                    "status": "needs_confirmation",
                    "unassessed_properties": critique["unassessed_properties"],
                },
                status="proposed",
            )
        )
    transition_project(
        session,
        project,
        target="waiting_for_user",
        actor_id=actor_id,
        reason="The bounded plan is ready for an explicit user comparison and selection.",
        details={"design_plan_id": plan.id, "risk_assessment_id": assessment.id},
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="design_plan.created",
            reason=(
                "A capped deterministic Template Matcher, Design Planner, and Design Critic "
                "flow paused for user selection."
            ),
            details={
                "design_plan_id": plan.id,
                "agent_run_id": run.id,
                "proposal_count": len(variants),
                "model_turn_limit": MAX_BOUNDED_MODEL_TURNS,
                "tool_call_limit": MAX_BOUNDED_TOOL_CALLS,
                "tool_calls": list(BOUNDED_PLAN_TOOL_CALLS),
            },
        )
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def select_plan_proposal(
    session: AsyncSession,
    *,
    project: Project,
    plan: DesignPlan,
    proposal: DesignPlanProposal,
    actor_id: str,
) -> DesignPlan:
    locked_plan = await _lock_plan(session, project_id=project.id, plan_id=plan.id)
    if locked_plan is None:
        raise RiskGateError("The design plan is unavailable.")
    plan = locked_plan
    await session.refresh(project)
    fresh_proposal = await session.scalar(
        select(DesignPlanProposal)
        .where(DesignPlanProposal.id == proposal.id, DesignPlanProposal.plan_id == plan.id)
        .execution_options(populate_existing=True)
    )
    if fresh_proposal is None:
        raise RiskGateError("This proposal is unavailable for selection.")
    proposal = fresh_proposal
    if plan.status != "waiting_for_user" or project.status != "waiting_for_user":
        raise RiskGateError("Only a current waiting-for-user plan can be selected.")
    if proposal.plan_id != plan.id or proposal.status != "proposed":
        raise RiskGateError("This proposal is not available for selection.")
    proposals = list(
        (
            await session.scalars(
                select(DesignPlanProposal)
                .where(DesignPlanProposal.plan_id == plan.id)
                .order_by(DesignPlanProposal.proposal_number.asc())
            )
        ).all()
    )
    for item in proposals:
        item.status = "selected" if item.id == proposal.id else "rejected"
    plan.status = "confirmed"
    transition_project(
        session,
        project,
        target="ready_for_generation",
        actor_id=actor_id,
        reason="The user selected one bounded DesignSpec variant from a reviewed plan.",
        details={"design_plan_id": plan.id, "design_plan_proposal_id": proposal.id},
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="design_plan.proposal_selected",
            reason="The user selected a bounded starting point; no approval or export occurred.",
            details={"design_plan_id": plan.id, "proposal_id": proposal.id},
        )
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def cancel_plan(
    session: AsyncSession,
    *,
    project: Project,
    plan: DesignPlan,
    actor_id: str,
) -> DesignPlan:
    locked_plan = await _lock_plan(session, project_id=project.id, plan_id=plan.id)
    if locked_plan is None:
        raise RiskGateError("The design plan is unavailable.")
    plan = locked_plan
    await session.refresh(project)
    if plan.status != "waiting_for_user" or project.status != "waiting_for_user":
        raise RiskGateError("Only a waiting-for-user plan can be cancelled.")
    plan.status = "cancelled"
    plan.cancelled_at = datetime.now(UTC)
    proposals = list(
        (
            await session.scalars(
                select(DesignPlanProposal).where(DesignPlanProposal.plan_id == plan.id)
            )
        ).all()
    )
    for proposal in proposals:
        if proposal.status == "proposed":
            proposal.status = "cancelled"
    transition_project(
        session,
        project,
        target="ready_for_generation",
        actor_id=actor_id,
        reason="The user cancelled the bounded plan before selecting a candidate starting point.",
        details={"design_plan_id": plan.id},
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="design_plan.cancelled",
            reason="The waiting-for-user design plan was cancelled without creating a candidate.",
            details={"design_plan_id": plan.id},
        )
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def queue_comparison_batch(
    session: AsyncSession,
    *,
    project: Project,
    assessment: RiskAssessment,
    plan: DesignPlan,
    actor_id: str,
    idempotency_key: str,
) -> QueuedComparison:
    """Queue all bounded plan variants only after an explicit user checkpoint.

    The route calls this after authenticating the owner. Every child is still
    re-checked independently by the worker before compilation, so this durable
    batch is orchestration metadata rather than an authorization shortcut.
    """

    project_id = project.id
    plan_id = plan.id
    existing = await session.scalar(
        select(CandidateGenerationBatch).where(
            CandidateGenerationBatch.project_id == project_id,
            CandidateGenerationBatch.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.design_plan_id != plan.id:
            raise RiskGateError(
                "This idempotency key was already used for a different comparison request."
            )
        existing_candidates = await _batch_candidates(session, existing.id)
        return QueuedComparison(batch=existing, candidates=tuple(existing_candidates), reused=True)
    # PostgreSQL serializes a user checkpoint here. SQLite ignores FOR UPDATE,
    # so the durable unique constraint below provides the equivalent final
    # arbitration across processes.
    locked_plan = await _lock_plan(session, project_id=project_id, plan_id=plan_id)
    if locked_plan is None:
        raise RiskGateError("The comparison plan is unavailable.")
    plan = locked_plan
    existing_for_plan = await session.scalar(
        select(CandidateGenerationBatch).where(CandidateGenerationBatch.design_plan_id == plan.id)
    )
    if existing_for_plan is not None:
        if existing_for_plan.idempotency_key != idempotency_key:
            raise RiskGateError(
                "This plan already has a durable private comparison batch. Create a new "
                "immutable plan to request another comparison."
            )
        existing_candidates = await _batch_candidates(session, existing_for_plan.id)
        return QueuedComparison(
            batch=existing_for_plan,
            candidates=tuple(existing_candidates),
            reused=True,
        )
    if project.status != "waiting_for_user" or plan.status != "waiting_for_user":
        raise RiskGateError("Only a current waiting-for-user plan can start a comparison batch.")
    if (
        assessment.status != "current"
        or assessment.tier != "R1"
        or plan.risk_assessment_id != assessment.id
    ):
        raise RiskGateError(
            "The comparison plan is not bound to the current deterministic R1 decision."
        )
    if "generate_candidate" not in assessment.allowed_actions:
        raise RiskGateError(
            "The current deterministic decision does not permit private candidates."
        )
    proposals = await _plan_proposals(session, plan.id)
    if not 2 <= len(proposals) <= 3 or any(item.status != "proposed" for item in proposals):
        raise RiskGateError("This plan no longer has two or three available bounded variants.")
    specifications: list[DesignSpecRevision] = []
    for proposal in proposals:
        specification = await session.scalar(
            select(DesignSpecRevision).where(
                DesignSpecRevision.id == proposal.design_spec_id,
                DesignSpecRevision.project_id == project.id,
            )
        )
        if specification is None:
            raise RiskGateError("A comparison variant is missing its immutable DesignSpec.")
        await assert_generation_allowed(
            session,
            project=project,
            design_spec=specification,
            expected_assessment_id=assessment.id,
            authorized_plan_id=plan.id,
        )
        specifications.append(specification)
    input_hash = canonical_hash(
        {
            "design_plan_id": plan.id,
            "risk_assessment_id": assessment.id,
            "decision_hash": assessment.decision_hash,
            "proposals": [
                {
                    "id": proposal.id,
                    "design_spec_id": specification.id,
                    "spec_hash": specification.spec_hash,
                    "variant_key": proposal.variant_key,
                }
                for proposal, specification in zip(proposals, specifications, strict=True)
            ],
        }
    )
    batch = CandidateGenerationBatch(
        project_id=project.id,
        design_plan_id=plan.id,
        risk_assessment_id=assessment.id,
        idempotency_key=idempotency_key,
        input_hash=input_hash,
        status="queued",
        requested_by=actor_id,
    )
    session.add(batch)
    await session.flush()
    next_candidate_number = await _next_candidate_number(session, project.id)
    candidates: list[CandidateDesign] = []
    for proposal, specification in zip(proposals, specifications, strict=True):
        document = DesignSpec.model_validate(specification.canonical_spec)
        candidate = CandidateDesign(
            project_id=project.id,
            design_spec_id=specification.id,
            risk_assessment_id=assessment.id,
            generation_batch_id=batch.id,
            variant_key=proposal.variant_key,
            variant_label=proposal.label,
            candidate_number=next_candidate_number,
            template_id=document.template_id,
            template_version=document.template_version,
            template_manifest_sha256=document.template_manifest_sha256,
            spec_hash=document.content_hash,
            generation_seed=document.generation_seed,
        )
        next_candidate_number += 1
        session.add(candidate)
        await session.flush()
        session.add(
            CadJob(
                project_id=project.id,
                candidate_id=candidate.id,
                idempotency_key=f"comparison:{batch.id}:{proposal.id}",
                input_hash=document.content_hash,
                requested_by=actor_id,
            )
        )
        proposal.status = "comparison_queued"
        candidates.append(candidate)
    plan.status = "comparison_queued"
    transition_project(
        session,
        project,
        target="generating",
        actor_id=actor_id,
        reason="The user confirmed a bounded private candidate comparison batch.",
        details={"design_plan_id": plan.id, "generation_batch_id": batch.id},
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="candidate_comparison.queued",
            reason=(
                "Two or three bounded reviewed-template variants were queued as private "
                "software candidates after an explicit user checkpoint."
            ),
            details={
                "design_plan_id": plan.id,
                "generation_batch_id": batch.id,
                "candidate_ids": [candidate.id for candidate in candidates],
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        # The database constraint is the fallback for concurrent SQLite
        # writers (and an additional defense on PostgreSQL). A competing
        # request has already made this checkpoint durable, so return its
        # immutable batch rather than creating or dispatching another one.
        await session.rollback()
        existing = await session.scalar(
            select(CandidateGenerationBatch).where(
                CandidateGenerationBatch.project_id == project_id,
                CandidateGenerationBatch.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            existing = await session.scalar(
                select(CandidateGenerationBatch).where(
                    CandidateGenerationBatch.design_plan_id == plan_id
                )
            )
        if existing is None:
            raise
        existing_candidates = await _batch_candidates(session, existing.id)
        return QueuedComparison(batch=existing, candidates=tuple(existing_candidates), reused=True)
    await session.refresh(batch)
    for candidate in candidates:
        await session.refresh(candidate)
    return QueuedComparison(batch=batch, candidates=tuple(candidates), reused=False)


async def cancel_comparison_batch(
    session: AsyncSession,
    *,
    project: Project,
    plan: DesignPlan,
    batch: CandidateGenerationBatch,
    actor_id: str,
) -> CandidateGenerationBatch:
    """Request cooperative cancellation for an entire private comparison batch."""

    batch_id = batch.id
    fresh_batch = await session.scalar(
        select(CandidateGenerationBatch)
        .where(CandidateGenerationBatch.id == batch_id)
        .execution_options(populate_existing=True)
    )
    if fresh_batch is None:
        raise RiskGateError("This comparison batch is unavailable.")
    batch = fresh_batch
    if batch.project_id != project.id or batch.design_plan_id != plan.id:
        raise RiskGateError("This comparison batch does not belong to the selected plan.")
    if batch.status in {"completed", "completed_with_failures", "failed", "cancelled"}:
        raise RiskGateError("This comparison batch is already terminal.")
    now = datetime.now(UTC)
    candidates = await _batch_candidates(session, batch.id)
    for candidate in candidates:
        # Child-level CAS updates preserve a completed compiler outcome when
        # it races a user cancellation. Workers use the same queued/running
        # states as their claim and finalization fences.
        queued = await session.execute(
            update(CandidateDesign)
            .where(CandidateDesign.id == candidate.id, CandidateDesign.status == "queued")
            .values(status="cancelled", completed_at=now)
        )
        if affected_row_count(queued) == 1:
            await session.execute(
                update(CadJob)
                .where(CadJob.candidate_id == candidate.id, CadJob.status == "queued")
                .values(
                    status="cancelled",
                    cancel_requested_at=now,
                    cancelled_at=now,
                    completed_at=now,
                )
            )
            continue
        running = await session.execute(
            update(CandidateDesign)
            .where(CandidateDesign.id == candidate.id, CandidateDesign.status == "running")
            .values(status="cancel_requested")
        )
        if affected_row_count(running) == 1:
            await session.execute(
                update(CadJob)
                .where(
                    CadJob.candidate_id == candidate.id,
                    CadJob.status == "running",
                    CadJob.cancel_requested_at.is_(None),
                )
                .values(cancel_requested_at=now)
            )
    cancellation_request = await session.execute(
        update(CandidateGenerationBatch)
        .where(
            CandidateGenerationBatch.id == batch.id,
            CandidateGenerationBatch.completed_at.is_(None),
            CandidateGenerationBatch.status.in_({"queued", "running", "cancellation_requested"}),
        )
        .values(cancel_requested_at=now)
    )
    if affected_row_count(cancellation_request) != 1:
        await session.rollback()
        raise RiskGateError("This comparison batch is already terminal.")
    await reconcile_comparison_batch(
        session,
        project=project,
        batch_id=batch.id,
        actor_id=actor_id,
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="candidate_comparison.cancel_requested",
            reason="The project owner cancelled or requested cancellation of a private comparison.",
            details={"design_plan_id": plan.id, "generation_batch_id": batch.id},
        )
    )
    await session.commit()
    await session.refresh(batch)
    return batch


async def select_compared_candidate(
    session: AsyncSession,
    *,
    project: Project,
    plan: DesignPlan,
    batch: CandidateGenerationBatch,
    candidate: CandidateDesign,
    actor_id: str,
) -> DesignPlan:
    """Record a post-comparison inspection choice without approving or exporting anything."""

    locked_plan = await _lock_plan(session, project_id=project.id, plan_id=plan.id)
    if locked_plan is None:
        raise RiskGateError("The design plan is unavailable.")
    plan = locked_plan
    await session.refresh(project)
    fresh_batch = await session.scalar(
        select(CandidateGenerationBatch)
        .where(CandidateGenerationBatch.id == batch.id)
        .execution_options(populate_existing=True)
    )
    if fresh_batch is None:
        raise RiskGateError("This comparison batch is unavailable.")
    batch = fresh_batch
    fresh_candidate = await session.scalar(
        select(CandidateDesign)
        .where(CandidateDesign.id == candidate.id)
        .execution_options(populate_existing=True)
    )
    if fresh_candidate is None:
        raise RiskGateError("This comparison candidate is unavailable.")
    candidate = fresh_candidate
    if (
        project.status != "candidates_ready"
        or plan.status != "comparison_ready"
        or batch.status not in {"completed", "completed_with_failures"}
    ):
        raise RiskGateError(
            "A completed private comparison is required before choosing a candidate."
        )
    if batch.project_id != project.id or batch.design_plan_id != plan.id:
        raise RiskGateError("This comparison batch does not belong to the selected plan.")
    if candidate.project_id != project.id or candidate.generation_batch_id != batch.id:
        raise RiskGateError("This candidate does not belong to the completed comparison batch.")
    if candidate.status != "succeeded":
        raise RiskGateError(
            "Only a successfully compiled private candidate can be selected for review."
        )
    proposals = await _plan_proposals(session, plan.id)
    matching = next(
        (item for item in proposals if item.design_spec_id == candidate.design_spec_id), None
    )
    if matching is None:
        raise RiskGateError("The candidate does not trace to a comparison-plan DesignSpec.")
    for proposal in proposals:
        proposal.status = (
            "comparison_selected" if proposal.id == matching.id else "comparison_ready"
        )
    plan.status = "comparison_selected"
    transition_project(
        session,
        project,
        target="user_review",
        actor_id=actor_id,
        reason="The user chose one private comparison candidate for software review only.",
        details={
            "design_plan_id": plan.id,
            "generation_batch_id": batch.id,
            "candidate_id": candidate.id,
        },
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="candidate_comparison.candidate_selected",
            reason=(
                "A completed private comparison candidate was selected for software review; "
                "no approval, export, manufacturing, or physical-use authorization occurred."
            ),
            details={
                "design_plan_id": plan.id,
                "generation_batch_id": batch.id,
                "candidate_id": candidate.id,
            },
        )
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def mark_comparison_batch_running(
    session: AsyncSession, *, batch_id: str | None
) -> CandidateGenerationBatch | None:
    if batch_id is None:
        return None
    await session.execute(
        update(CandidateGenerationBatch)
        .where(
            CandidateGenerationBatch.id == batch_id,
            CandidateGenerationBatch.status == "queued",
            CandidateGenerationBatch.cancel_requested_at.is_(None),
        )
        .values(status="running")
    )
    return cast(
        CandidateGenerationBatch | None,
        await session.scalar(
            select(CandidateGenerationBatch)
            .where(CandidateGenerationBatch.id == batch_id)
            .execution_options(populate_existing=True)
        ),
    )


async def reconcile_comparison_batch(
    session: AsyncSession,
    *,
    project: Project,
    batch_id: str | None,
    actor_id: str,
) -> CandidateGenerationBatch | None:
    """Advance project state only when every child in a batch is terminal."""

    if batch_id is None:
        return None
    # Flush the terminal child before acquiring the batch row. With a real row
    # lock this makes exactly one worker observe and finalize the last child;
    # SQLite's writer serialization and the same durable status check provide
    # the corresponding local behavior.
    await session.flush()
    batch = await session.scalar(
        select(CandidateGenerationBatch)
        .where(CandidateGenerationBatch.id == batch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if batch is None:
        return None
    candidates = await _batch_candidates(session, batch.id)
    pending = {"queued", "running", "cancel_requested"}
    if any(candidate.status in pending for candidate in candidates):
        batch.status = "cancellation_requested" if batch.cancel_requested_at else "running"
        return batch
    if batch.completed_at is not None:
        return batch
    now = datetime.now(UTC)
    succeeded = [candidate for candidate in candidates if candidate.status == "succeeded"]
    cancelled = [candidate for candidate in candidates if candidate.status == "cancelled"]
    if succeeded:
        batch.status = (
            "completed" if len(succeeded) == len(candidates) else "completed_with_failures"
        )
    elif cancelled and len(cancelled) == len(candidates):
        batch.status = "cancelled"
    else:
        batch.status = "failed"
    batch.completed_at = now
    plan = await session.get(DesignPlan, batch.design_plan_id)
    if plan is None:  # pragma: no cover - protected by the non-null FK
        raise RiskGateError("A comparison batch is missing its immutable plan lineage.")
    proposals = await _plan_proposals(session, plan.id)
    if succeeded:
        plan.status = "comparison_ready"
        for proposal in proposals:
            if proposal.status == "comparison_queued":
                proposal.status = "comparison_ready"
    elif batch.status == "cancelled":
        plan.status = "comparison_cancelled"
        plan.cancelled_at = now
        for proposal in proposals:
            if proposal.status == "comparison_queued":
                proposal.status = "cancelled"
    else:
        plan.status = "comparison_failed"
    if project.status == "generating":
        transition_project(
            session,
            project,
            target="candidates_ready" if succeeded else "ready_for_generation",
            actor_id=actor_id,
            reason=(
                "Every private comparison job reached a terminal state; the batch outcome was "
                "recorded without approval or export."
            ),
            details={"generation_batch_id": batch.id, "batch_status": batch.status},
        )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="candidate_comparison.completed",
            reason="All private comparison jobs are terminal and the batch outcome is recorded.",
            details={"generation_batch_id": batch.id, "batch_status": batch.status},
        )
    )
    return batch


async def record_comparison_dispatch_deferred(
    session: AsyncSession,
    *,
    project: Project,
    batch: CandidateGenerationBatch,
    actor_id: str,
    error: Exception,
) -> None:
    """Audit an uncertain broker publish while leaving durable work queued.

    A queued CadJob is the transactional outbox record. The periodic dispatcher
    and idempotent API replay can safely publish it again; an API-side broker
    exception is not proof that the broker did not receive the message.
    """

    detail = str(error).replace("\n", " ")[:500] or "The comparison jobs could not be submitted."
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="candidate_comparison.queue_submission_deferred",
            reason=(
                "The broker publish was uncertain, so the durable private comparison jobs remain "
                "queued for idempotent recovery."
            ),
            details={"generation_batch_id": batch.id, "error": detail},
        )
    )
    await session.commit()


async def _plan_proposals(session: AsyncSession, plan_id: str) -> list[DesignPlanProposal]:
    return list(
        (
            await session.scalars(
                select(DesignPlanProposal)
                .where(DesignPlanProposal.plan_id == plan_id)
                .order_by(DesignPlanProposal.proposal_number.asc())
            )
        ).all()
    )


async def _batch_candidates(session: AsyncSession, batch_id: str) -> list[CandidateDesign]:
    return list(
        (
            await session.scalars(
                select(CandidateDesign)
                .where(CandidateDesign.generation_batch_id == batch_id)
                .order_by(CandidateDesign.candidate_number.asc())
                .execution_options(populate_existing=True)
            )
        ).all()
    )


async def _next_candidate_number(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        select(func.max(CandidateDesign.candidate_number)).where(
            CandidateDesign.project_id == project_id
        )
    )
    return int(value or 0) + 1


async def _persist_variant_spec(
    session: AsyncSession,
    *,
    project: Project,
    source_spec: DesignSpecRevision,
    assessment: RiskAssessment,
    variant: PlannedVariant,
    actor_id: str,
) -> str:
    document = variant.design_spec
    validate_design_spec(document)
    revision = DesignSpecRevision(
        project_id=project.id,
        requirements_revision_id=source_spec.requirements_revision_id,
        parent_design_spec_id=source_spec.id,
        risk_assessment_id=assessment.id,
        revision_number=await _next_spec_number(session, project.id),
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
    return revision.id


async def _next_plan_number(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        select(func.max(DesignPlan.plan_number)).where(DesignPlan.project_id == project_id)
    )
    return int(value or 0) + 1


async def _next_spec_number(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        select(func.max(DesignSpecRevision.revision_number)).where(
            DesignSpecRevision.project_id == project_id
        )
    )
    return int(value or 0) + 1
