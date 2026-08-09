"""Deterministic Template Matcher, Design Planner, and Design Critic roles.

These roles are a small, inspectable state machine rather than a free-running
model loop.  A future optional language-model narration may describe these
records, but it cannot change template selection, parameter values, risk, or
validation outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass

from accessforge.cad.registry import (
    TemplateRegistryError,
    get_template_release,
    parameter_values_mm,
    validate_design_spec,
)
from accessforge.cad.schemas import CanonicalLength, DesignSpec, FieldProvenance


@dataclass(frozen=True)
class PlannedVariant:
    """A bounded parameter alternative accepted by the reviewed registry."""

    key: str
    label: str
    design_spec: DesignSpec
    rationale: str
    tradeoffs: tuple[str, ...]
    uses_source_spec: bool = False


def template_match(spec: DesignSpec) -> list[dict[str, object]]:
    """Return exactly the already risk-bound reviewed release, never a search guess."""

    release = get_template_release(spec.template_id, spec.template_version)
    return [
        {
            "template_id": release.manifest.template_id,
            "template_version": release.manifest.version,
            "template_manifest_sha256": release.manifest_sha256,
            "match_type": "hard_constraint_match",
            "explanation": (
                "The risk-bound DesignSpec fixes this repository-reviewed template release. "
                "The matcher cannot select a different or unreviewed template."
            ),
        }
    ]


def critic_summary(variants: list[PlannedVariant]) -> dict[str, object]:
    """Return conservative, structured critique without claiming any result is safe."""

    return {
        "role": "design_critic",
        "status": "needs_confirmation",
        "candidate_count": len(variants),
        "unassessed_properties": [
            "physical fit and retention",
            "strength, fatigue life, and material behavior",
            "comfort, skin compatibility, and accessibility outcome",
            "printability and physical safety",
        ],
        "explanation": (
            "These variants passed only deterministic template-range and geometry-contract "
            "checks before compilation. Compare their recorded parameter tradeoffs; none is "
            "approved for manufacture, physical use, or export."
        ),
    }


def plan_variants(spec: DesignSpec) -> list[PlannedVariant]:
    """Produce two or three meaningful, server-validated variants when possible.

    The first alternative is the exact risk-bound input.  Subsequent alternatives
    move one geometry dimension toward a compact or generous bounded direction.
    Every prospective document is checked by the same static registry before it
    can leave the planner.
    """

    validate_design_spec(spec)
    variants = [
        PlannedVariant(
            key="balanced",
            label="Recorded dimensions",
            design_spec=spec,
            rationale="Uses the exact dimensions from the risk-bound DesignSpec.",
            tradeoffs=(
                "Preserves the original recorded dimensions.",
                "Does not establish physical fit, strength, or comfort.",
            ),
            uses_source_spec=True,
        )
    ]
    compact = _first_valid_adjustment(spec, direction="compact")
    if compact is not None:
        variants.append(compact)
    generous = _first_valid_adjustment(spec, direction="generous")
    if generous is not None:
        variants.append(generous)
    return variants[:3]


def _first_valid_adjustment(spec: DesignSpec, *, direction: str) -> PlannedVariant | None:
    release = get_template_release(spec.template_id, spec.template_version)
    preferred_names = (
        ("grip_length", "sleeve_length", "pull_loop_outer_height", "pull_loop_outer_width")
        if direction == "compact"
        else (
            "outer_diameter",
            "pull_loop_outer_width",
            "pull_loop_outer_height",
            "grip_length",
            "sleeve_length",
        )
    )
    for name in preferred_names:
        definition = release.manifest.parameters.get(name)
        if definition is None:
            continue
        current_mm = parameter_values_mm(spec)[name]
        target_mm = _toward_bound(
            current=current_mm,
            minimum=definition.minimum,
            maximum=definition.maximum,
            direction=direction,
        )
        if abs(target_mm - current_mm) < 0.001:
            continue
        candidate = _with_adjusted_parameter(
            spec, name=name, value_mm=target_mm, direction=direction
        )
        try:
            validate_design_spec(candidate)
        except TemplateRegistryError:
            continue
        label = "Compact geometry" if direction == "compact" else "Generous geometry"
        tradeoff = (
            f"Adjusts {name.replace('_', ' ')} from {current_mm:g} mm to {target_mm:g} mm.",
            (
                "The parameter difference is a deterministic comparison aid, not a fit "
                "or performance prediction."
            ),
        )
        return PlannedVariant(
            key=direction,
            label=label,
            design_spec=candidate,
            rationale=(
                f"The bounded planner moved {name.replace('_', ' ')} toward the reviewed "
                f"{direction} range while preserving the template contract."
            ),
            tradeoffs=tradeoff,
        )
    return None


def _toward_bound(*, current: float, minimum: float, maximum: float, direction: str) -> float:
    if direction == "compact":
        target = minimum + (current - minimum) * 0.45
    else:
        target = maximum - (maximum - current) * 0.45
    return round(target, 6)


def _with_adjusted_parameter(
    spec: DesignSpec, *, name: str, value_mm: float, direction: str
) -> DesignSpec:
    parameters = dict(spec.parameters)
    parameters[name] = CanonicalLength(
        canonical_value_m=value_mm / 1000,
        original_value=value_mm,
        original_unit="mm",
    )
    provenance = dict(spec.field_provenance)
    provenance[f"parameters.{name}"] = FieldProvenance(
        creator_type="rule",
        source_ref=f"rule:bounded-design-planner.v1:{direction}:{name}",
        rationale=(
            "A bounded deterministic planner created this comparison-only parameter variant "
            "from a risk-bound reviewed-template DesignSpec."
        ),
    )
    return spec.model_copy(update={"parameters": parameters, "field_provenance": provenance})
