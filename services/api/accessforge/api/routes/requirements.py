"""Human-confirmed requirements proposals backed by the provider boundary.

This route deliberately persists only typed proposals and safe operational
metadata.  It never accepts geometry, safety assertions, raw provider payloads,
or raw media as an AI input.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.ai.configuration import credential_for_config
from accessforge.ai.prompt_registry import get_prompt
from accessforge.ai.providers import ModelProviderError
from accessforge.ai.schemas.requirements import RequirementRevisionInput
from accessforge.ai.security import CredentialSecurityError
from accessforge.ai.workflows.requirements import (
    WorkflowStepCheckpoint,
    run_requirements_workflow,
)
from accessforge.core.config import get_settings
from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import (
    AgentRun,
    AgentStep,
    AuditEvent,
    ConsentRecord,
    ModelProviderConfig,
    Project,
    Requirement,
    RequirementRevision,
    utc_now,
)
from accessforge.db.session import get_session
from accessforge.projects.workflow import get_owned_project, transition_project
from accessforge.requirements.service import (
    SUPPORTED_DATA_CATEGORIES,
    build_project_context,
    canonical_hash,
    persist_requirement_revision,
    validate_citations,
)

router = APIRouter(prefix="/v1/projects/{project_id}/requirements", tags=["requirements"])


class RequirementsExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_config_id: str | None = Field(default=None, min_length=1, max_length=36)


class RequirementRead(BaseModel):
    id: str
    kind: str
    value_number: float | None
    value_text: str | None
    unit: str | None
    source_refs: list[str]
    source: str
    confidence: float | None
    needs_confirmation: bool
    explanation: str
    provenance: dict[str, object]
    created_at: datetime


class RequirementRevisionRead(BaseModel):
    id: str
    revision_number: int
    source: str
    status: str
    agent_run_id: str | None
    provider_config_id: str | None
    prompt_id: str | None
    prompt_hash: str | None
    requirements: list[RequirementRead]
    unknowns: list[dict[str, object]]
    clarifying_questions: list[dict[str, object]]
    risk_signals: list[dict[str, object]]
    rationale: str | None
    content_hash: str
    created_at: datetime
    confirmed_at: datetime | None
    confirmed_by: str | None


def _string_items(values: Iterable[object]) -> list[str]:
    return [value for value in values if isinstance(value, str)]


def _object_records(values: Iterable[object] | None) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for value in values or ():
        if isinstance(value, dict) and all(isinstance(key, str) for key in value):
            records.append(dict(value))
    return records


async def serialize_revision(
    session: AsyncSession, revision: RequirementRevision
) -> RequirementRevisionRead:
    requirements = list(
        (
            await session.scalars(
                select(Requirement)
                .where(Requirement.revision_id == revision.id)
                .order_by(Requirement.created_at.asc())
            )
        ).all()
    )
    return RequirementRevisionRead(
        id=revision.id,
        revision_number=revision.revision_number,
        source=revision.source,
        status=revision.status,
        agent_run_id=revision.agent_run_id,
        provider_config_id=revision.provider_config_id,
        prompt_id=revision.prompt_id,
        prompt_hash=revision.prompt_hash,
        requirements=[
            RequirementRead(
                id=requirement.id,
                kind=requirement.kind,
                value_number=requirement.value_number,
                value_text=requirement.value_text,
                unit=requirement.unit,
                source_refs=_string_items(requirement.source_refs),
                source=requirement.source,
                confidence=requirement.confidence,
                needs_confirmation=requirement.needs_confirmation,
                explanation=requirement.explanation,
                provenance=requirement.provenance,
                created_at=requirement.created_at,
            )
            for requirement in requirements
        ],
        unknowns=_object_records(revision.unknowns),
        clarifying_questions=_object_records(revision.clarifying_questions),
        risk_signals=_object_records(revision.risk_signals),
        rationale=revision.rationale,
        content_hash=revision.content_hash,
        created_at=revision.created_at,
        confirmed_at=revision.confirmed_at,
        confirmed_by=revision.confirmed_by,
    )


async def get_owned_provider_config(
    session: AsyncSession, principal: Principal, config_id: str
) -> ModelProviderConfig:
    config = await session.scalar(
        select(ModelProviderConfig).where(
            ModelProviderConfig.id == config_id,
            ModelProviderConfig.owner_id == principal.subject,
        )
    )
    if config is None or config.status == "revoked":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model configuration not found."
        )
    return config


async def has_external_ai_consent(session: AsyncSession, project: Project) -> bool:
    granted_consent = await session.scalar(
        select(ConsentRecord.id)
        .where(
            ConsentRecord.project_id == project.id,
            ConsentRecord.consent_type == "ai_provider_sharing",
            ConsentRecord.granted.is_(True),
            ConsentRecord.revoked_at.is_(None),
        )
        .order_by(ConsentRecord.recorded_at.desc())
        .limit(1)
    )
    return granted_consent is not None


def ensure_requirements_state(project: Project) -> None:
    if project.scope_status == "blocked" or project.status == "blocked_out_of_scope":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This project is outside the supported scope and cannot request AI assistance.",
        )
    if project.status not in {"captured", "requirements_pending", "requirements_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete project capture before requesting an editable requirements proposal.",
        )


def ensure_structured_output_capability(config: ModelProviderConfig) -> None:
    capabilities = config.capabilities or {}
    if capabilities.get("structured_json") != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test this model configuration for structured JSON support before using it.",
        )


def sum_known(*values: int | None) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def estimate_cost_usd(
    config: ModelProviderConfig,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Return an operator-configured estimate without hard-coding vendor prices."""

    if config.provider_type == "fake":
        return 0.0
    if (
        input_tokens is None
        or output_tokens is None
        or config.input_cost_per_million_usd is None
        or config.output_cost_per_million_usd is None
    ):
        return None
    return round(
        (
            (input_tokens * config.input_cost_per_million_usd)
            + (output_tokens * config.output_cost_per_million_usd)
        )
        / 1_000_000,
        8,
    )


async def mark_run_failed(
    session: AsyncSession,
    run: AgentRun,
    steps: list[AgentStep],
    *,
    error_category: str,
) -> None:
    run.status = "failed"
    run.error_category = error_category
    run.updated_at = utc_now()
    run.version += 1
    for step in steps:
        if step.status != "completed":
            step.status = "failed"
            step.error_category = error_category
    await session.commit()


@router.get("", response_model=list[RequirementRevisionRead])
async def list_requirements(
    project_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[RequirementRevisionRead]:
    project = await get_owned_project(session, principal, project_id)
    revisions = list(
        (
            await session.scalars(
                select(RequirementRevision)
                .where(RequirementRevision.project_id == project.id)
                .order_by(RequirementRevision.revision_number.desc())
            )
        ).all()
    )
    return [await serialize_revision(session, revision) for revision in revisions]


@router.post(
    ":extract", response_model=RequirementRevisionRead, status_code=status.HTTP_201_CREATED
)
async def extract_requirements(
    project_id: str,
    payload: RequirementsExtractRequest,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> RequirementRevisionRead:
    project = await get_owned_project(session, principal, project_id)
    ensure_requirements_state(project)
    selected_config_id = payload.provider_config_id or project.model_provider_config_id
    if not selected_config_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose a tested model configuration or continue without AI assistance.",
        )
    config = await get_owned_provider_config(session, principal, selected_config_id)
    if config.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test this model configuration successfully before using it.",
        )
    ensure_structured_output_capability(config)
    if config.provider_type != "fake" and not await has_external_ai_consent(session, project):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Record separate AI-provider sharing consent before sending project "
                "data externally."
            ),
        )

    project_context, allowed_source_refs = await build_project_context(
        session, project, config.allowed_data_categories
    )
    extractor_prompt = get_prompt("requirements_extractor")
    if project.status == "captured":
        transition_project(
            session,
            project,
            target="requirements_pending",
            actor_id=principal.subject,
            reason="A requirements proposal was requested.",
            details={"provider_config_id": config.id},
        )
    project.model_provider_config_id = config.id
    run = AgentRun(
        project_id=project.id,
        provider_config_id=config.id,
        workflow_type="requirements_assistant",
        provider_type=config.provider_type,
        model_identifier=config.fast_model or config.reasoning_model,
        status="running",
        prompt_id=f"{extractor_prompt.identifier}:{extractor_prompt.version}",
        prompt_hash=extractor_prompt.content_hash,
        input_hash=canonical_hash(project_context),
    )
    session.add(run)
    await session.flush()
    extractor_step = AgentStep(
        agent_run_id=run.id,
        step_number=1,
        name="requirements_extractor",
        status="running",
        tool_name="model_provider",
        input_hash=canonical_hash(project_context),
    )
    clarification_step = AgentStep(
        agent_run_id=run.id,
        step_number=2,
        name="clarification_planner",
        status="queued",
        tool_name="model_provider",
    )
    session.add_all((extractor_step, clarification_step))
    await session.commit()

    async def checkpoint(metadata: WorkflowStepCheckpoint) -> None:
        step = extractor_step if metadata.name == "requirements_extractor" else clarification_step
        step.status = "completed"
        step.input_hash = metadata.input_hash
        step.output_hash = metadata.output_hash
        step.latency_ms = metadata.latency_ms
        step.error_category = None
        await session.commit()

    credential: str | None = None
    try:
        credential = credential_for_config(config, get_settings())
        workflow = await run_requirements_workflow(
            config=config,
            credential=credential,
            settings=get_settings(),
            project_context=project_context,
            on_step_completed=checkpoint,
            correlation_id=run.id,
        )
        validate_citations(workflow.extraction, allowed_source_refs)
        revision = await persist_requirement_revision(
            session,
            project=project,
            content=workflow.extraction,
            source="ai_proposal",
            status_value="draft",
            created_by=principal.subject,
            agent_run=run,
            provider_config_id=config.id,
            prompt_id=(
                f"{workflow.extractor_prompt.identifier}:{workflow.extractor_prompt.version}"
            ),
            prompt_hash=workflow.extractor_prompt.content_hash,
        )
        run.status = "succeeded"
        run.input_tokens = sum_known(
            workflow.extraction_result.completion.usage.input_tokens,
            workflow.clarification_result.completion.usage.input_tokens,
        )
        run.output_tokens = sum_known(
            workflow.extraction_result.completion.usage.output_tokens,
            workflow.clarification_result.completion.usage.output_tokens,
        )
        run.estimated_cost_usd = estimate_cost_usd(
            config,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
        )
        run.latency_ms = sum_known(
            workflow.extraction_result.completion.latency_ms,
            workflow.clarification_result.completion.latency_ms,
        )
        run.output_hash = canonical_hash(workflow.extraction.model_dump(mode="json"))
        run.result_rationale = workflow.extraction.rationale
        run.updated_at = utc_now()
        run.version += 1
        if project.status == "requirements_pending":
            transition_project(
                session,
                project,
                target="requirements_review",
                actor_id=principal.subject,
                reason="A typed requirements proposal is ready for user review.",
                details={"agent_run_id": run.id, "revision_id": revision.id},
            )
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id=principal.subject,
                event_type="requirements.extracted",
                reason="AI created an editable, source-linked requirements proposal.",
                details={"agent_run_id": run.id, "revision_id": revision.id},
            )
        )
        await session.commit()
        return await serialize_revision(session, revision)
    except HTTPException:
        await mark_run_failed(
            session, run, [extractor_step, clarification_step], error_category="validation_error"
        )
        raise
    except (CredentialSecurityError, ModelProviderError, ValueError) as exc:
        error_category = getattr(exc, "code", "provider_configuration_error")
        await mark_run_failed(
            session, run, [extractor_step, clarification_step], error_category=error_category
        )
        provider_response_problem = error_category in {
            "provider_response_error",
            "structured_output_error",
        }
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT if provider_response_problem else 502
            ),
            detail=(
                "The provider returned a response that could not be safely accepted."
                if provider_response_problem
                else "The selected model provider could not complete this request."
            ),
        ) from exc
    except Exception as exc:
        await mark_run_failed(
            session, run, [extractor_step, clarification_step], error_category="unexpected_error"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The selected model provider could not complete this request.",
        ) from exc
    finally:
        credential = None


@router.post("/{revision_id}:confirm", response_model=RequirementRevisionRead)
async def confirm_requirements(
    project_id: str,
    revision_id: str,
    payload: RequirementRevisionInput,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> RequirementRevisionRead:
    project = await get_owned_project(session, principal, project_id)
    revision = await session.scalar(
        select(RequirementRevision).where(
            RequirementRevision.id == revision_id,
            RequirementRevision.project_id == project.id,
        )
    )
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Requirements revision not found."
        )
    if project.status != "requirements_review" or revision.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending requirements proposal can be confirmed.",
        )
    if project.active_requirement_revision_id != revision.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Confirm the current requirements proposal or create a new one.",
        )
    _, allowed_source_refs = await build_project_context(
        session, project, SUPPORTED_DATA_CATEGORIES
    )
    validate_citations(payload, allowed_source_refs, allow_user_confirmation=True)
    confirmed = await persist_requirement_revision(
        session,
        project=project,
        content=payload,
        source="user_confirmation",
        status_value="confirmed",
        created_by=principal.subject,
    )
    transition_project(
        session,
        project,
        target="risk_review",
        actor_id=principal.subject,
        reason="User confirmed an immutable requirements revision.",
        details={"source_revision_id": revision.id, "confirmed_revision_id": confirmed.id},
    )
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=principal.subject,
            event_type="requirements.confirmed",
            reason="User reviewed and confirmed editable requirements.",
            details={"source_revision_id": revision.id, "confirmed_revision_id": confirmed.id},
        )
    )
    await session.commit()
    return await serialize_revision(session, confirmed)
