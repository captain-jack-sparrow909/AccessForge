import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.ai.schemas.requirements import (
    ClarifyingQuestion,
    RequirementProposal,
    RequirementRevisionInput,
    RequirementsExtractionResponse,
    RiskSignal,
    UnknownItem,
)
from accessforge.db.models import (
    AgentRun,
    Measurement,
    Observation,
    Project,
    Requirement,
    RequirementRevision,
)

SUPPORTED_DATA_CATEGORIES = frozenset({"project_text", "measurements"})


def canonical_hash(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def build_project_context(
    session: AsyncSession, project: Project, data_categories: Iterable[object]
) -> tuple[dict[str, object], set[str]]:
    categories = {category for category in data_categories if isinstance(category, str)}
    if not categories.issubset(SUPPORTED_DATA_CATEGORIES):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provider configuration contains an unsupported data category.",
        )
    if not categories:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose project text and/or measurements before requesting AI assistance.",
        )
    context: dict[str, object] = {
        "project_id": project.id,
        "scope_status": project.scope_status,
        "scope_reason": project.scope_reason,
        "allowed_source_refs": [],
    }
    source_refs: set[str] = set()
    if "project_text" in categories:
        project_facts = {
            "goal": project.goal,
            "object_description": project.object_description,
            "action_description": project.action_description,
            "environment": project.environment,
            "load_context": project.load_context,
        }
        context["project_text"] = {
            key: value for key, value in project_facts.items() if value is not None
        }
        source_refs.update(f"project:{key}" for key, value in project_facts.items() if value)
        observations = list(
            (
                await session.scalars(
                    select(Observation)
                    .where(Observation.project_id == project.id, Observation.input_mode == "text")
                    .order_by(Observation.created_at.asc())
                )
            ).all()
        )
        context["observations"] = [
            {"source_id": f"observation:{item.id}", "text": item.text} for item in observations
        ]
        source_refs.update(f"observation:{item.id}" for item in observations)
    if "measurements" in categories:
        measurements = list(
            (
                await session.scalars(
                    select(Measurement)
                    .where(Measurement.project_id == project.id)
                    .order_by(Measurement.created_at.asc())
                )
            ).all()
        )
        context["measurements"] = [
            {
                "source_id": f"measurement:{item.id}",
                "kind": item.kind,
                "value": item.value,
                "unit": item.unit,
                "canonical_value_mm": item.canonical_value_mm,
                "tolerance": item.tolerance,
                "confirmed": item.confirmed,
                "unknown": item.unknown,
                "method": item.method,
            }
            for item in measurements
        ]
        source_refs.update(f"measurement:{item.id}" for item in measurements)
    context["allowed_source_refs"] = sorted(source_refs)
    return context, source_refs


def validate_citations(
    response: RequirementsExtractionResponse | RequirementRevisionInput,
    allowed_source_refs: set[str],
    *,
    allow_user_confirmation: bool = False,
) -> None:
    cited: set[str] = set()
    for requirement in response.requirements:
        cited.update(requirement.source_refs)
    for unknown in response.unknowns:
        cited.update(unknown.source_refs)
    for signal in response.risk_signals:
        cited.update(signal.source_refs)
    for question in response.clarifying_questions:
        cited.update(question.related_source_refs)
    permitted_source_refs = set(allowed_source_refs)
    if allow_user_confirmation:
        # A user can add a requirement during confirmation even when no existing
        # project fact expresses it. This explicit marker is unavailable to a
        # provider proposal and preserves honest provenance.
        permitted_source_refs.add("user:confirmation")
    nonexistent = cited - permitted_source_refs
    if nonexistent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The model response cited project data that was not supplied.",
        )


def proposal_payload(item: RequirementProposal) -> dict[str, object]:
    return item.model_dump(mode="json")


def response_payload(
    response: RequirementsExtractionResponse | RequirementRevisionInput,
) -> dict[str, object]:
    return response.model_dump(mode="json")


async def next_revision_number(session: AsyncSession, project_id: str) -> int:
    value = await session.scalar(
        select(func.max(RequirementRevision.revision_number)).where(
            RequirementRevision.project_id == project_id
        )
    )
    return int(value or 0) + 1


async def persist_requirement_revision(
    session: AsyncSession,
    *,
    project: Project,
    content: RequirementsExtractionResponse | RequirementRevisionInput,
    source: str,
    status_value: str,
    created_by: str,
    agent_run: AgentRun | None = None,
    provider_config_id: str | None = None,
    prompt_id: str | None = None,
    prompt_hash: str | None = None,
) -> RequirementRevision:
    payload = response_payload(content)
    revision = RequirementRevision(
        project_id=project.id,
        revision_number=await next_revision_number(session, project.id),
        source=source,
        status=status_value,
        agent_run_id=agent_run.id if agent_run else None,
        provider_config_id=provider_config_id,
        prompt_id=prompt_id,
        prompt_hash=prompt_hash,
        unknowns=[item.model_dump(mode="json") for item in content.unknowns],
        clarifying_questions=[
            item.model_dump(mode="json") for item in content.clarifying_questions
        ],
        risk_signals=[item.model_dump(mode="json") for item in content.risk_signals],
        rationale=content.rationale,
        content_hash=canonical_hash(payload),
        created_by=created_by,
        confirmed_at=datetime.now(UTC) if status_value == "confirmed" else None,
        confirmed_by=created_by if status_value == "confirmed" else None,
    )
    session.add(revision)
    await session.flush()
    creator_type = "ai_proposal" if source == "ai_proposal" else "user"
    for item in content.requirements:
        session.add(
            Requirement(
                project_id=project.id,
                revision_id=revision.id,
                kind=item.kind,
                value_number=item.value_number,
                value_text=item.value_text,
                unit=item.unit,
                source_refs=list(item.source_refs),
                source=source,
                confidence=item.confidence,
                needs_confirmation=item.needs_confirmation,
                explanation=item.explanation,
                provenance={
                    "creator_type": creator_type,
                    "source_refs": list(item.source_refs),
                    "confidence": item.confidence,
                },
            )
        )
    project.active_requirement_revision_id = revision.id
    project.version += 1
    return revision


def extraction_from_parts(
    *,
    requirements: list[RequirementProposal],
    unknowns: list[UnknownItem],
    clarifying_questions: list[ClarifyingQuestion],
    risk_signals: list[RiskSignal],
    rationale: str,
) -> RequirementsExtractionResponse:
    return RequirementsExtractionResponse(
        requirements=requirements,
        unknowns=unknowns,
        clarifying_questions=clarifying_questions,
        risk_signals=risk_signals,
        rationale=rationale,
    )
