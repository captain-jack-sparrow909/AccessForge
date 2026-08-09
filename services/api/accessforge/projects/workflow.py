from collections.abc import Mapping

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.core.security import Principal
from accessforge.db.models import AuditEvent, Project, User

PROJECT_STATES = (
    "draft",
    "consented",
    "captured",
    "requirements_pending",
    "requirements_review",
    "risk_review",
    "ready_for_generation",
    "planning",
    "waiting_for_user",
    "generating",
    "candidates_ready",
    "user_review",
    "approved",
    "export_ready",
    "blocked_out_of_scope",
    "needs_more_information",
    "cancelled",
    "deleted",
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"consented", "blocked_out_of_scope", "needs_more_information", "deleted"},
    "consented": {"captured", "blocked_out_of_scope", "needs_more_information", "deleted"},
    "captured": {"requirements_pending", "needs_more_information", "deleted"},
    "requirements_pending": {"requirements_review", "needs_more_information", "deleted"},
    "requirements_review": {"risk_review", "needs_more_information", "deleted"},
    "risk_review": {
        "ready_for_generation",
        "needs_more_information",
        "blocked_out_of_scope",
        "deleted",
    },
    "ready_for_generation": {"risk_review", "planning", "generating", "deleted"},
    "planning": {"waiting_for_user", "risk_review", "deleted"},
    "waiting_for_user": {"ready_for_generation", "risk_review", "generating", "deleted"},
    "generating": {
        "ready_for_generation",
        "candidates_ready",
        "risk_review",
        "cancelled",
        "deleted",
    },
    "candidates_ready": {"user_review", "deleted"},
    "user_review": {"approved", "generating", "deleted"},
    "approved": {"export_ready", "deleted"},
    "export_ready": {"deleted"},
    "blocked_out_of_scope": {"risk_review", "deleted"},
    "needs_more_information": {"consented", "captured", "risk_review", "deleted"},
    "cancelled": {"deleted"},
    "deleted": set(),
}


def evaluate_scope(
    *,
    action: str | None,
    object_description: str | None,
    environment: str | None,
    load_context: str | None,
    safety_system: bool | None,
    age_context: str | None,
) -> tuple[str, str]:
    """Run a conservative, deterministic Phase 2 pre-screen.

    This intentionally does not decide whether a design is safe. It only detects
    obvious out-of-scope signals and keeps unknowns visible for later review.
    """

    combined = " ".join(
        value.lower() for value in (action, object_description, environment, age_context) if value
    )
    prohibited_terms = (
        "wheelchair",
        "body weight",
        "transfer",
        "vehicle",
        "brake",
        "steering",
        "medicine",
        "medication",
        "child safety",
        "power tool",
        "mains electricity",
        "high voltage",
        "fire",
        "gas",
        "hot surface",
        "oven",
        "weapon",
    )
    if safety_system is True:
        return "blocked", "The object is described as part of a safety or access-control system."
    if any(term in combined for term in prohibited_terms):
        return "blocked", "This request appears outside the low-risk grip and pull MVP boundary."
    if load_context and load_context.lower() in {"high", "body_weight", "unknown"}:
        return (
            "needs_confirmation",
            "The load or force context needs confirmation before generation.",
        )
    if safety_system is None or not action or not object_description or not environment:
        return (
            "needs_confirmation",
            "Some scope details are unknown; generation must pause until clarified.",
        )
    return "supported", "The description is within the initial passive grip and pull scope."


async def ensure_user(session: AsyncSession, principal: Principal) -> User:
    user = await session.get(User, principal.subject)
    if user is None:
        user = User(id=principal.subject, email=principal.email)
        session.add(user)
        await session.flush()
    elif principal.email and user.email != principal.email:
        user.email = principal.email
    return user


async def get_owned_project(
    session: AsyncSession, principal: Principal, project_id: str, *, include_deleted: bool = False
) -> Project:
    from sqlalchemy import select

    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == principal.subject)
    )
    if project is None or (project.status == "deleted" and not include_deleted):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def assert_transition(project: Project, target: str) -> None:
    if target not in PROJECT_STATES:
        raise ValueError(f"Unknown project state: {target}")
    if target == project.status:
        return
    if target not in ALLOWED_TRANSITIONS.get(project.status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project cannot move from {project.status} to {target}.",
        )


def transition_project(
    session: AsyncSession,
    project: Project,
    *,
    target: str,
    actor_id: str,
    reason: str,
    details: Mapping[str, object] | None = None,
) -> None:
    assert_transition(project, target)
    if target == project.status:
        return
    previous = project.status
    project.status = target
    project.version += 1
    session.add(
        AuditEvent(
            project_id=project.id,
            actor_id=actor_id,
            event_type="project.state_changed",
            from_state=previous,
            to_state=target,
            reason=reason,
            details=dict(details) if details else None,
        )
    )
