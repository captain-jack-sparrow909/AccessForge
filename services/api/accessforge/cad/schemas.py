"""Immutable, versioned DesignSpec domain schemas.

The API creates these documents from explicit, unit-bearing user entries.  A
compiler receives only their canonical SI values and a fixed template release.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from accessforge.cad.units import normalize_unit, to_metres

CreatorType = Literal["user", "measurement", "rule", "ai_proposal", "template_default", "reviewer"]
RiskTier = Literal["R0", "R1", "R2", "R3"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldProvenance(FrozenModel):
    """Who supplied a field and the concise reason it may be used."""

    creator_type: CreatorType
    source_ref: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=1000)


class CanonicalLength(FrozenModel):
    """A canonical metre value plus the exact original entry for provenance."""

    canonical_value_m: float = Field(gt=0, le=10)
    canonical_unit: Literal["m"] = "m"
    original_value: float = Field(gt=0, le=100_000)
    original_unit: Literal["m", "mm", "cm", "in"]

    @model_validator(mode="after")
    def original_value_matches_canonical_value(self) -> CanonicalLength:
        expected = to_metres(self.original_value, self.original_unit)
        if not math.isclose(self.canonical_value_m, expected, abs_tol=0.000000001):
            raise ValueError("Canonical length does not match the original unit-bearing entry.")
        return self


class ManufacturingProfile(FrozenModel):
    process: Literal["fdm"]
    material_profile: Literal["pla_provisional", "petg_provisional"]
    nozzle_diameter: CanonicalLength
    layer_height: CanonicalLength


class DesignSpec(FrozenModel):
    """The sole structured input accepted by a trusted template compiler."""

    schema_version: Literal["1.0"] = "1.0"
    project_id: str = Field(min_length=1, max_length=36)
    requirements_revision_id: str = Field(min_length=1, max_length=36)
    template_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    template_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    template_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parameters: dict[str, CanonicalLength] = Field(min_length=1, max_length=30)
    manufacturing: ManufacturingProfile
    fit_clearance: CanonicalLength
    dimensional_tolerance: CanonicalLength
    uses_assessed: tuple[str, ...] = Field(min_length=1, max_length=20)
    uses_not_assessed: tuple[str, ...] = Field(min_length=1, max_length=20)
    risk_tier: RiskTier
    risk_rule_set_version: str = Field(min_length=1, max_length=120)
    confirmed_assumptions: tuple[str, ...] = Field(max_length=30)
    unresolved_assumptions: tuple[str, ...] = Field(max_length=30)
    generation_seed: str = Field(min_length=1, max_length=120)
    field_provenance: dict[str, FieldProvenance] = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def every_compiler_input_has_provenance(self) -> DesignSpec:
        required = {
            "schema_version",
            "project_id",
            "requirements_revision_id",
            "template_id",
            "template_version",
            "template_manifest_sha256",
            "manufacturing",
            "manufacturing.nozzle_diameter",
            "manufacturing.layer_height",
            "fit_clearance",
            "dimensional_tolerance",
            "uses_assessed",
            "uses_not_assessed",
            "risk_tier",
            "risk_rule_set_version",
            "confirmed_assumptions",
            "unresolved_assumptions",
            "generation_seed",
        }
        required.update(f"parameters.{name}" for name in self.parameters)
        supplied = set(self.field_provenance)
        missing = sorted(required - supplied)
        unexpected = sorted(supplied - required)
        if missing or unexpected:
            details: list[str] = []
            if missing:
                details.append(f"missing provenance for {', '.join(missing)}")
            if unexpected:
                details.append(f"unexpected provenance for {', '.join(unexpected)}")
            raise ValueError("; ".join(details))
        return self

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    @property
    def content_hash(self) -> str:
        return canonical_hash(self.canonical_payload())


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_length_from_entry(value: float, unit: str) -> CanonicalLength:
    # ``normalize_unit`` validates this runtime string against the same closed
    # set used by ``CanonicalLength``.  Retain that narrowed fact for the typed
    # immutable boundary without changing the unit-conversion behavior.
    normalized_unit = cast(Literal["m", "mm", "cm", "in"], normalize_unit(unit))
    return CanonicalLength(
        canonical_value_m=to_metres(value, normalized_unit),
        original_value=value,
        original_unit=normalized_unit,
    )
