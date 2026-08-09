"""Closed, immutable inputs and outputs for deterministic risk assessment."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskTier = Literal["R0", "R1", "R2", "R3"]
RiskFindingStatus = Literal["matched", "not_assessed"]

TIER_RANK: dict[RiskTier, int] = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}


class FrozenRiskModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RiskContextInput(FrozenRiskModel):
    """Explicit risk facts that cannot be inferred or silently defaulted."""

    intended_use: str = Field(min_length=3, max_length=2000)
    body_contact: Literal["none", "incidental", "prolonged", "unknown"]
    load: Literal["none", "low_energy_occasional", "repetitive", "high", "body_weight", "unknown"]
    temperature: Literal["room_temperature", "hot", "cold", "unknown"]
    chemicals: Literal["none", "household", "laboratory", "unknown"]
    electricity: Literal["none", "low_voltage", "mains", "unknown"]
    age_group: Literal["adult", "child", "unknown"]
    safety_feature_interaction: Literal["none", "possible", "yes", "unknown"]
    failure_consequence: Literal[
        "minor_inconvenience", "loss_of_access", "injury", "safety_critical", "unknown"
    ]
    duration: Literal["occasional", "prolonged", "unknown"]
    fatigue: Literal["not_expected", "possible", "likely", "unknown"]
    manufacturing_uncertainty: Literal["bounded", "provisional", "unknown"]


class RiskEvidence(FrozenRiskModel):
    """A source identifier only—never raw media, private prompts, or credentials."""

    source_ref: str = Field(min_length=1, max_length=240)
    field: str = Field(min_length=1, max_length=160)


class RiskFinding(FrozenRiskModel):
    rule_id: str = Field(min_length=1, max_length=160)
    rule_version: str = Field(min_length=1, max_length=80)
    tier: RiskTier
    status: RiskFindingStatus = "matched"
    evidence: tuple[RiskEvidence, ...] = Field(min_length=1, max_length=30)
    explanation: str = Field(min_length=1, max_length=2000)
    remediation: str | None = Field(default=None, max_length=2000)


class RiskDecision(FrozenRiskModel):
    tier: RiskTier
    ruleset_version: str = Field(min_length=1, max_length=120)
    ruleset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    matched_findings: tuple[RiskFinding, ...]
    unresolved_questions: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    user_explanation: str = Field(min_length=1, max_length=4000)
