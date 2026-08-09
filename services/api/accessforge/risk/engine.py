"""Pure, monotonic evaluator for the Phase 5 MVP risk policy.

The evaluator consumes typed context and conservative source references. It
never accepts a model-provided tier, never emits raw project content, and only
ever raises the maximum matched tier.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from importlib import resources
from typing import cast

from accessforge.cad.registry import TemplateRegistryError, get_template_release
from accessforge.risk.schemas import (
    TIER_RANK,
    RiskContextInput,
    RiskDecision,
    RiskEvidence,
    RiskFinding,
    RiskTier,
)


def _load_ruleset() -> tuple[dict[str, object], str]:
    raw = resources.files("accessforge.risk").joinpath("ruleset-v1.json").read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):  # pragma: no cover - static package integrity guard
        raise RuntimeError("The deterministic risk ruleset must be an object.")
    return cast(dict[str, object], payload), hashlib.sha256(raw).hexdigest()


RULESET, RULESET_HASH = _load_ruleset()
RULESET_VERSION = str(RULESET["version"])


def evaluate_risk(
    context: RiskContextInput,
    project_facts: Mapping[str, object],
    requirement_signals: Iterable[Mapping[str, object]],
    source_refs: Iterable[str],
    template_id: str,
    template_version: str,
    template_manifest_sha256: str,
    has_confirmed_requirements: bool,
    spec_unresolved_assumptions: Iterable[str],
) -> RiskDecision:
    """Return a fully deterministic, fail-closed tier and audit explanation."""

    known_refs = frozenset(source_refs)
    findings: list[RiskFinding] = []
    unresolved: list[str] = []
    tier: RiskTier = "R1"

    def add(
        rule_id: str,
        matched_tier: RiskTier,
        explanation: str,
        *,
        refs: Iterable[str],
        fields: Iterable[str],
        remediation: str | None,
    ) -> None:
        nonlocal tier
        evidence = tuple(
            RiskEvidence(source_ref=_safe_ref(ref, known_refs), field=field)
            for ref, field in zip(refs, fields, strict=False)
        )
        if not evidence:
            evidence = (RiskEvidence(source_ref="risk:context", field="risk_context"),)
        findings.append(
            RiskFinding(
                rule_id=rule_id,
                rule_version=RULESET_VERSION,
                tier=matched_tier,
                evidence=evidence,
                explanation=explanation,
                remediation=remediation,
            )
        )
        if TIER_RANK[matched_tier] > TIER_RANK[tier]:
            tier = matched_tier

    _apply_text_rules(context, project_facts, known_refs, add)
    _apply_closed_context_rules(context, add, unresolved)
    _apply_project_rules(project_facts, add, unresolved)
    _apply_requirement_signals(requirement_signals, known_refs, add, unresolved)
    _apply_template_rule(template_id, template_version, template_manifest_sha256, add, unresolved)
    if not has_confirmed_requirements:
        tier = "R0" if tier == "R1" else tier
        unresolved.append("Confirm an immutable requirements revision before requesting geometry.")
        add(
            "R0-confirmed-requirements-required",
            "R0",
            (
                "A confirmed immutable requirements revision is required before this "
                "workflow can assess geometry."
            ),
            refs=("risk:requirements",),
            fields=("requirements_revision",),
            remediation=(
                "Review and confirm the requirements before rerunning deterministic risk "
                "assessment."
            ),
        )
    unresolved_assumptions = tuple(item for item in spec_unresolved_assumptions if item.strip())
    if unresolved_assumptions:
        unresolved.append("Resolve every DesignSpec assumption before automatic generation.")
        add(
            "R2-unresolved-design-spec-assumptions",
            "R2",
            (
                "The immutable DesignSpec retains unresolved assumptions that can affect "
                "the requested geometry."
            ),
            refs=("risk:design-spec",),
            fields=("unresolved_assumptions",),
            remediation=(
                "Resolve the recorded assumptions and create a new immutable risk-bound DesignSpec."
            ),
        )
    if tier == "R1" and unresolved:
        tier = "R2"
    if tier == "R1":
        add(
            "R1-reviewed-passive-mvp-boundary",
            "R1",
            (
                "All supplied facts describe the narrow reviewed passive MVP boundary; "
                "this permits private software generation only."
            ),
            refs=("risk:context", "risk:template"),
            fields=("risk_context", "reviewed_template"),
            remediation=None,
        )
    return RiskDecision(
        tier=tier,
        ruleset_version=RULESET_VERSION,
        ruleset_hash=RULESET_HASH,
        matched_findings=tuple(findings),
        unresolved_questions=tuple(dict.fromkeys(unresolved)),
        allowed_actions=_allowed_actions(tier),
        user_explanation=_user_explanation(tier),
    )


def _apply_text_rules(
    context: RiskContextInput,
    project_facts: Mapping[str, object],
    known_refs: frozenset[str],
    add: object,
) -> None:
    adder = cast("_RiskAdder", add)
    text_records: list[tuple[str, str, str]] = [
        ("risk:intended-use", "intended_use", context.intended_use)
    ]
    supplied = project_facts.get("text_sources")
    if isinstance(supplied, Mapping):
        for ref, value in supplied.items():
            if isinstance(ref, str) and isinstance(value, str):
                text_records.append((_safe_ref(ref, known_refs), ref.split(":")[-1], value))
    combined = "\n".join(value.casefold() for _, _, value in text_records)
    prohibited = _string_list(RULESET.get("prohibited_text_terms"))
    if any(term in combined for term in prohibited):
        refs, fields = _matching_text_evidence(text_records, prohibited)
        adder(
            "R3-prohibited-mvp-domain",
            "R3",
            (
                "The requested use intersects a prohibited mobility, safety-control, medical, "
                "weapon, bypass, heat, gas, electrical, chemical, pressure, or workflow-bypass "
                "domain."
            ),
            refs=refs,
            fields=fields,
            remediation=(
                "Do not generate geometry. Seek an appropriate qualified professional or "
                "safer non-geometry resource."
            ),
        )
    professional = _string_list(RULESET.get("professional_review_text_terms"))
    if any(term in combined for term in professional):
        refs, fields = _matching_text_evidence(text_records, professional)
        adder(
            "R2-context-needs-professional-review",
            "R2",
            (
                "The supplied text describes an environment or contact pattern outside the "
                "automatic low-risk MVP boundary."
            ),
            refs=refs,
            fields=fields,
            remediation=(
                "Automatic generation is blocked; clarify scope or request qualified review."
            ),
        )


def _apply_closed_context_rules(
    context: RiskContextInput, add: object, unresolved: list[str]
) -> None:
    adder = cast("_RiskAdder", add)
    if context.load == "body_weight":
        adder(
            "R3-body-weight-load",
            "R3",
            "Body-weight or transfer load is outside the automatic MVP boundary.",
            refs=("risk:context",),
            fields=("load",),
            remediation="Do not generate geometry for body-weight or transfer use.",
        )
    if context.electricity == "mains":
        adder(
            "R3-mains-electricity",
            "R3",
            "Mains-electricity interaction is outside the automatic MVP boundary.",
            refs=("risk:context",),
            fields=("electricity",),
            remediation="Do not generate geometry for electrical control or mains interaction.",
        )
    if context.safety_feature_interaction == "yes":
        adder(
            "R3-safety-feature-interaction",
            "R3",
            (
                "The requested object is described as interacting with a safety or "
                "access-control feature."
            ),
            refs=("risk:context",),
            fields=("safety_feature_interaction",),
            remediation=(
                "Do not generate geometry for safety-feature or access-control interaction."
            ),
        )
    if context.failure_consequence in {"injury", "safety_critical"}:
        adder(
            "R3-severe-failure-consequence",
            "R3",
            "The stated failure consequence can include injury or a safety-critical outcome.",
            refs=("risk:context",),
            fields=("failure_consequence",),
            remediation="Do not generate geometry for this failure consequence.",
        )
    r2_values: tuple[tuple[str, str, set[str], str], ...] = (
        ("body_contact", context.body_contact, {"prolonged", "unknown"}, "body-contact risk"),
        (
            "load",
            context.load,
            {"none", "repetitive", "high", "unknown"},
            "load uncertainty or repetition",
        ),
        ("temperature", context.temperature, {"hot", "cold", "unknown"}, "temperature context"),
        (
            "chemicals",
            context.chemicals,
            {"household", "laboratory", "unknown"},
            "chemical exposure",
        ),
        ("electricity", context.electricity, {"low_voltage", "unknown"}, "electrical context"),
        ("age_group", context.age_group, {"child", "unknown"}, "age context"),
        (
            "safety_feature_interaction",
            context.safety_feature_interaction,
            {"possible", "unknown"},
            "safety-feature context",
        ),
        (
            "failure_consequence",
            context.failure_consequence,
            {"loss_of_access", "unknown"},
            "failure consequence",
        ),
        ("duration", context.duration, {"prolonged", "unknown"}, "duration"),
        ("fatigue", context.fatigue, {"possible", "likely", "unknown"}, "fatigue or repetition"),
        (
            "manufacturing_uncertainty",
            context.manufacturing_uncertainty,
            {"provisional", "unknown"},
            "manufacturing uncertainty",
        ),
    )
    for field, value, blocked_values, label in r2_values:
        if value not in blocked_values:
            continue
        if value == "unknown":
            unresolved.append(f"Confirm {field.replace('_', ' ')} before automatic generation.")
        adder(
            f"R2-{field}",
            "R2",
            f"The supplied {label} is outside the complete low-risk automatic-generation boundary.",
            refs=("risk:context",),
            fields=(field,),
            remediation=(
                "Automatic generation is blocked; clarify the fact or request qualified review."
            ),
        )


def _apply_project_rules(
    project_facts: Mapping[str, object], add: object, unresolved: list[str]
) -> None:
    adder = cast("_RiskAdder", add)
    scope_status = project_facts.get("scope_status")
    if scope_status == "blocked":
        adder(
            "R3-project-scope-blocked",
            "R3",
            (
                "The deterministic project pre-screen already marked this request outside "
                "the MVP scope."
            ),
            refs=("project:scope_status",),
            fields=("scope_status",),
            remediation="Do not generate geometry for this project scope.",
        )
    elif scope_status != "supported":
        unresolved.append("Resolve the project scope pre-screen before automatic generation.")
        adder(
            "R2-project-scope-unresolved",
            "R2",
            "The project scope pre-screen is not supported and cannot permit automatic generation.",
            refs=("project:scope_status",),
            fields=("scope_status",),
            remediation="Clarify the project scope before rerunning risk assessment.",
        )
    if project_facts.get("safety_system") is True:
        adder(
            "R3-project-safety-system",
            "R3",
            "The project identifies a safety-system interaction, which is prohibited in this MVP.",
            refs=("project:safety_system",),
            fields=("safety_system",),
            remediation="Do not generate geometry for safety-system interaction.",
        )


def _apply_requirement_signals(
    signals: Iterable[Mapping[str, object]],
    known_refs: frozenset[str],
    add: object,
    unresolved: list[str],
) -> None:
    adder = cast("_RiskAdder", add)
    for signal in signals:
        level = signal.get("level")
        refs_value = signal.get("source_refs")
        refs = (
            tuple(_safe_ref(ref, known_refs) for ref in refs_value if isinstance(ref, str))
            if isinstance(refs_value, list)
            else ("risk:requirements",)
        )
        if level == "blocked":
            adder(
                "R3-confirmed-requirement-risk-signal",
                "R3",
                "A confirmed requirements revision contains a blocking risk signal.",
                refs=refs,
                fields=("requirements.risk_signal",) * len(refs),
                remediation="Do not generate geometry while this blocking signal remains.",
            )
        elif level == "needs_confirmation":
            unresolved.append("Resolve the confirmed requirements revision risk signal.")
            adder(
                "R2-confirmed-requirement-risk-signal",
                "R2",
                (
                    "A confirmed requirements revision retains a risk signal needing "
                    "clarification or review."
                ),
                refs=refs,
                fields=("requirements.risk_signal",) * len(refs),
                remediation="Resolve the signal before automatic generation.",
            )


def _apply_template_rule(
    template_id: str,
    template_version: str,
    manifest_sha256: str,
    add: object,
    unresolved: list[str],
) -> None:
    adder = cast("_RiskAdder", add)
    try:
        release = get_template_release(template_id, template_version)
        is_reviewed = release.manifest_sha256 == manifest_sha256 and template_id in _string_list(
            RULESET.get("r1_templates")
        )
    except TemplateRegistryError:
        is_reviewed = False
    if not is_reviewed:
        unresolved.append(
            "Use an exact repository-reviewed template release before automatic generation."
        )
        adder(
            "R2-reviewed-template-required",
            "R2",
            (
                "The selected template release is unavailable, changed, or outside the "
                "reviewed automatic MVP set."
            ),
            refs=("risk:template",),
            fields=("template_release",),
            remediation="Select a current exact repository-reviewed template release.",
        )


def _allowed_actions(tier: RiskTier) -> tuple[str, ...]:
    if tier == "R1":
        return ("view_risk_report", "create_design_plan", "generate_candidate")
    if tier == "R2":
        return ("view_risk_report", "revise_requirements", "request_professional_review")
    if tier == "R3":
        return ("view_risk_report", "revise_requirements")
    return ("view_risk_report", "complete_requirements")


def _user_explanation(tier: RiskTier) -> str:
    if tier == "R1":
        return (
            "This is within the narrow reviewed passive MVP boundary for private software "
            "generation. It is not a safety finding, physical-use approval, manufacturing "
            "instruction, or export permission."
        )
    if tier == "R2":
        return (
            "Automatic generation and export are blocked because this request needs "
            "clarification or qualified review. You can review the recorded reasons and "
            "revise confirmed facts."
        )
    if tier == "R3":
        return (
            "This request is prohibited for automatic geometry in the current MVP. No "
            "candidate is generated; seek an appropriate qualified professional or safer "
            "non-geometry resource."
        )
    return (
        "Complete the required facts and immutable requirements review before geometry can "
        "be assessed."
    )


def _safe_ref(value: str, known_refs: frozenset[str]) -> str:
    return (
        value
        if value in known_refs or value.startswith("risk:") or value.startswith("project:")
        else "risk:context"
    )


def _string_list(value: object) -> tuple[str, ...]:
    return (
        tuple(item.casefold() for item in value if isinstance(item, str))
        if isinstance(value, list)
        else ()
    )


def _matching_text_evidence(
    records: Iterable[tuple[str, str, str]], terms: Iterable[str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    refs: list[str] = []
    fields: list[str] = []
    terms_tuple = tuple(terms)
    for ref, field, text in records:
        if any(term in text.casefold() for term in terms_tuple):
            refs.append(ref)
            fields.append(field)
    return tuple(refs) or ("risk:context",), tuple(fields) or ("risk_context",)


class _RiskAdder:
    def __call__(
        self,
        rule_id: str,
        matched_tier: RiskTier,
        explanation: str,
        *,
        refs: Iterable[str],
        fields: Iterable[str],
        remediation: str | None,
    ) -> None: ...
