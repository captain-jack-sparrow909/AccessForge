"""Versioned, non-human controlled-validation evidence schema.

The protocol records what a qualified reviewer observed on dimensional fixtures
and physical coupons.  It is an evidence-capture boundary, not a claim that a
candidate is fit, safe, durable, printable, or appropriate for a person.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTROLLED_VALIDATION_PROTOCOL_VERSION = "phase6-controlled-fixture.v1"
STOP_CRITERIA = frozenset(
    {
        "crack",
        "sharp_edge",
        "unexpected_deformation",
        "detachment",
        "fit_failure",
        "measurement_tool_issue",
        "other_stop",
    }
)


class _ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PhysicalProcessRecordInput(_ProtocolModel):
    process: Literal["fdm"]
    material_profile: Literal["pla_provisional", "petg_provisional"]
    printer_reference: str = Field(min_length=1, max_length=160)
    material_batch_reference: str = Field(min_length=1, max_length=160)
    orientation_record: str = Field(min_length=1, max_length=1000)
    nozzle_diameter_mm: float = Field(gt=0, le=5)
    layer_height_mm: float = Field(gt=0, le=2)
    calibration_reference: str = Field(min_length=1, max_length=500)


class RecordedDimensionInput(_ProtocolModel):
    label: str = Field(min_length=1, max_length=160)
    nominal_mm: float = Field(gt=0, le=500)
    observed_mm: float = Field(gt=0, le=500)
    tolerance_mm: float = Field(gt=0, le=25)

    @property
    def within_recorded_tolerance(self) -> bool:
        return abs(self.observed_mm - self.nominal_mm) <= self.tolerance_mm


class ControlledPhysicalValidationInput(_ProtocolModel):
    protocol_version: Literal["phase6-controlled-fixture.v1"]
    record_type: Literal["dimensional_fixture", "physical_coupon"]
    process_record: PhysicalProcessRecordInput
    measured_dimensions: tuple[RecordedDimensionInput, ...] = Field(min_length=1, max_length=20)
    stop_criteria_observed: tuple[str, ...] = Field(default_factory=tuple, max_length=10)
    evidence_hashes: tuple[str, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def valid_stop_criteria_and_hashes(self) -> ControlledPhysicalValidationInput:
        if any(value not in STOP_CRITERIA for value in self.stop_criteria_observed):
            raise ValueError("A controlled validation record has an unsupported stop criterion.")
        if not all(
            len(value) == 64 and all(character in "0123456789abcdef" for character in value)
            for value in self.evidence_hashes
        ):
            raise ValueError(
                "Controlled validation evidence hashes must be lowercase SHA-256 values."
            )
        return self


def recorded_result(payload: ControlledPhysicalValidationInput) -> str:
    """Derive an observation status; never accept a caller-provided pass claim."""

    if payload.stop_criteria_observed:
        return "stopped_for_recorded_criterion"
    if all(item.within_recorded_tolerance for item in payload.measured_dimensions):
        return "within_recorded_tolerance"
    return "outside_recorded_tolerance"


def protocol_summary() -> dict[str, object]:
    """Return user-visible protocol boundaries without a physical-use assertion."""

    return {
        "version": CONTROLLED_VALIDATION_PROTOCOL_VERSION,
        "scope": "Non-human dimensional fixtures and physical coupons only.",
        "required_record_types": ["dimensional_fixture", "physical_coupon"],
        "stop_criteria": sorted(STOP_CRITERIA),
        "limitations": (
            "A recorded result does not establish safety, fit, comfort, strength, durability, "
            "printability, material suitability, or accessibility benefit."
        ),
    }
