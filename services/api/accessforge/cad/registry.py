"""Static allowlist for repository-reviewed template releases.

The mapping below is deliberately data, not plugin discovery.  A caller can
select a documented template identifier and exact release, but never an import
path, a file path, or arbitrary template code.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from accessforge.cad.schemas import DesignSpec
from accessforge.cad.units import metres_to_mm


class TemplateRegistryError(ValueError):
    """A DesignSpec cannot be resolved to a reviewed template release."""


class TemplateParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=160)
    unit: str = "mm"
    minimum: float = Field(gt=0, le=500)
    maximum: float = Field(gt=0, le=500)
    default: float = Field(gt=0, le=500)
    description: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def range_contains_default(self) -> TemplateParameter:
        if self.unit != "mm":
            raise ValueError("Built-in mechanical template parameters must declare millimetres.")
        if self.minimum > self.maximum:
            raise ValueError("Parameter minimum cannot exceed its maximum.")
        if not self.minimum <= self.default <= self.maximum:
            raise ValueError("Parameter default must be inside the accepted range.")
        return self


class TemplateManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_schema_version: str = Field(min_length=1, max_length=20)
    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    status: str = Field(min_length=1, max_length=120)
    supported_uses: tuple[str, ...] = Field(min_length=1, max_length=20)
    prohibited_uses: tuple[str, ...] = Field(min_length=1, max_length=30)
    parameters: dict[str, TemplateParameter] = Field(min_length=1, max_length=30)
    expected_dimensions: dict[str, object] = Field(min_length=1, max_length=10)
    validation_policy: dict[str, object] = Field(min_length=1, max_length=20)
    print_guidance: dict[str, str] = Field(min_length=1, max_length=20)
    known_limitations: tuple[str, ...] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def manifest_is_review_only(self) -> TemplateManifest:
        if self.status != "reviewed_repository_only":
            raise ValueError("Only reviewed repository template releases may be executable.")
        return self


@dataclass(frozen=True)
class TemplateRelease:
    manifest: TemplateManifest
    manifest_bytes: bytes
    manifest_sha256: str
    release_path: Path

    @property
    def key(self) -> tuple[str, str]:
        return self.manifest.template_id, self.manifest.version


# Do not turn this into globbing, entry-point discovery, a database lookup, or a
# user-controlled module name.  Adding a template is an explicit code review.
_REVIEWED_RELEASES: dict[tuple[str, str], str] = {
    ("pull_tab_extender", "1.0.0"): "pull_tab_extender/1.0.0/manifest.yaml",
    ("cylindrical_grip_thickener", "1.0.0"): "cylindrical_grip_thickener/1.0.0/manifest.yaml",
    ("handle_sleeve", "1.0.0"): "handle_sleeve/1.0.0/manifest.yaml",
}


def _asset_root() -> Path:
    return Path(str(files("accessforge.cad").joinpath("template_assets")))


def _read_release(template_id: str, version: str) -> TemplateRelease:
    relative_path = _REVIEWED_RELEASES.get((template_id, version))
    if relative_path is None:
        raise TemplateRegistryError("This template release is not reviewed and executable.")
    root = _asset_root().resolve()
    path = (root / relative_path).resolve()
    if root not in path.parents or path.suffix != ".yaml":
        raise TemplateRegistryError("Template manifest path is invalid.")
    try:
        manifest_bytes = path.read_bytes()
        # Template paths are hard-coded above, and safe_load rejects executable
        # Python tags.  The exact reviewed bytes remain content-addressed below.
        payload = yaml.safe_load(manifest_bytes)
    except (OSError, yaml.YAMLError) as exc:
        raise TemplateRegistryError(
            "Reviewed template manifest is unavailable or invalid."
        ) from exc
    if not isinstance(payload, dict):
        raise TemplateRegistryError("Reviewed template manifest must contain an object.")
    manifest = TemplateManifest.model_validate(payload)
    if manifest.template_id != template_id or manifest.version != version:
        raise TemplateRegistryError(
            "Template manifest identity does not match its reviewed release."
        )
    return TemplateRelease(
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        release_path=path.parent,
    )


def get_template_release(template_id: str, version: str) -> TemplateRelease:
    return _read_release(template_id, version)


def list_template_releases() -> list[TemplateRelease]:
    return [
        _read_release(template_id, version) for template_id, version in sorted(_REVIEWED_RELEASES)
    ]


def validate_design_spec(spec: DesignSpec) -> TemplateRelease:
    """Verify identity and all deterministic pre-geometry constraints.

    This deliberately has no CadQuery import.  Range and cross-parameter
    failures reject an immutable record before a compiler process starts, and
    the fixed generator repeats the checks as defence in depth.
    """

    release = get_template_release(spec.template_id, spec.template_version)
    if spec.template_manifest_sha256 != release.manifest_sha256:
        raise TemplateRegistryError("The DesignSpec does not reference the reviewed manifest hash.")
    expected_names = set(release.manifest.parameters)
    supplied_names = set(spec.parameters)
    if supplied_names != expected_names:
        missing = sorted(expected_names - supplied_names)
        unexpected = sorted(supplied_names - expected_names)
        reason: list[str] = []
        if missing:
            reason.append(f"missing: {', '.join(missing)}")
        if unexpected:
            reason.append(f"unexpected: {', '.join(unexpected)}")
        raise TemplateRegistryError(
            f"Template parameters must match exactly ({'; '.join(reason)})."
        )
    for name, definition in release.manifest.parameters.items():
        value_mm = metres_to_mm(spec.parameters[name].canonical_value_m)
        if not definition.minimum <= value_mm <= definition.maximum:
            raise TemplateRegistryError(
                f"{name} must be between {definition.minimum:g} and {definition.maximum:g} mm; "
                "AccessForge never silently clamps a design parameter."
            )
    _validate_template_contract(spec.template_id, parameter_values_mm(spec))
    return release


def parameter_values_mm(spec: DesignSpec) -> Mapping[str, float]:
    return {name: metres_to_mm(value.canonical_value_m) for name, value in spec.parameters.items()}


def _validate_template_contract(template_id: str, values: Mapping[str, float]) -> None:
    if template_id == "pull_tab_extender":
        _validate_pull_tab_contract(values)
    elif template_id == "cylindrical_grip_thickener":
        _validate_split_sleeve_contract(
            inner_diameter=values["inner_diameter"],
            outer_diameter=values["outer_diameter"],
            length=values["grip_length"],
            slit_width=values["slit_width"],
            edge_radius=values["edge_radius"],
            context="cylindrical grip thickener",
        )
    elif template_id == "handle_sleeve":
        _validate_split_sleeve_contract(
            inner_diameter=values["handle_diameter"] + 2 * values["fit_clearance"],
            outer_diameter=values["outer_diameter"],
            length=values["sleeve_length"],
            slit_width=values["slit_width"],
            edge_radius=values["edge_radius"],
            context="handle sleeve",
        )


def _validate_pull_tab_contract(values: Mapping[str, float]) -> None:
    outer_width = values["pull_loop_outer_width"]
    outer_height = values["pull_loop_outer_height"]
    edge_radius = values["edge_radius"]
    slot_width = values["attachment_slot_width"] + 2 * values["attachment_clearance"]
    slot_height = values["attachment_slot_height"] + 2 * values["attachment_clearance"]
    if outer_width < slot_width + 2 * edge_radius:
        raise TemplateRegistryError(
            "The pull-tab width leaves insufficient material around the attachment slot."
        )
    if outer_height < slot_height + 4 * edge_radius:
        raise TemplateRegistryError(
            "The pull-tab height leaves insufficient material around the attachment slot."
        )
    if edge_radius > min(outer_width, outer_height) / 2:
        raise TemplateRegistryError(
            "The requested pull-tab edge radius is too large for its dimensions."
        )


def _validate_split_sleeve_contract(
    *,
    inner_diameter: float,
    outer_diameter: float,
    length: float,
    slit_width: float,
    edge_radius: float,
    context: str,
) -> None:
    if outer_diameter <= inner_diameter:
        raise TemplateRegistryError(f"The {context} outer diameter must exceed its inner diameter.")
    wall = (outer_diameter - inner_diameter) / 2
    if wall < 2.4:
        raise TemplateRegistryError(
            f"The {context} wall must be at least 2.4 mm in this provisional release."
        )
    if slit_width >= outer_diameter / 2:
        raise TemplateRegistryError(f"The {context} slit is too wide.")
    if edge_radius > min(wall / 2, length / 4):
        raise TemplateRegistryError(
            f"The {context} edge radius is too large for its wall or length."
        )
