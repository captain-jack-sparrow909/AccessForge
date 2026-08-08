from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequirementProposal(BaseModel):
    """A proposed, editable requirement; never a CAD parameter or safety verdict."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern=r"^[a-z][a-z0-9_]{1,118}$")
    value_number: float | None = None
    value_text: str | None = Field(default=None, max_length=2000)
    unit: str | None = Field(default=None, max_length=40)
    source_refs: list[str] = Field(min_length=1, max_length=20)
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = True
    explanation: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def validate_value(self) -> "RequirementProposal":
        if (self.value_number is None) == (self.value_text is None):
            raise ValueError("A requirement needs exactly one numeric or text value.")
        if self.value_number is not None and not self.unit:
            raise ValueError("Numeric requirements must include a unit.")
        if self.value_text is not None and self.unit is not None:
            raise ValueError("Text requirements cannot include a unit.")
        return self


class UnknownItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern=r"^[a-z][a-z0-9_]{1,118}$")
    explanation: str = Field(min_length=1, max_length=1200)
    source_refs: list[str] = Field(min_length=1, max_length=20)


class ClarifyingQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,118}$")
    question: str = Field(min_length=1, max_length=1200)
    why_it_matters: str = Field(min_length=1, max_length=1200)
    priority: int = Field(ge=1, le=5)
    related_source_refs: list[str] = Field(default_factory=list, max_length=20)


class RiskSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern=r"^[a-z][a-z0-9_]{1,118}$")
    level: Literal["needs_confirmation", "blocked"]
    explanation: str = Field(min_length=1, max_length=1200)
    source_refs: list[str] = Field(min_length=1, max_length=20)


class RequirementsExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: list[RequirementProposal] = Field(default_factory=list, max_length=30)
    unknowns: list[UnknownItem] = Field(default_factory=list, max_length=30)
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list, max_length=10)
    risk_signals: list[RiskSignal] = Field(default_factory=list, max_length=20)
    rationale: str = Field(min_length=1, max_length=2000)


class ClarificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list, max_length=10)
    rationale: str = Field(min_length=1, max_length=2000)


class RequirementRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: list[RequirementProposal] = Field(default_factory=list, max_length=30)
    unknowns: list[UnknownItem] = Field(default_factory=list, max_length=30)
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list, max_length=10)
    risk_signals: list[RiskSignal] = Field(default_factory=list, max_length=20)
    rationale: str | None = Field(default=None, max_length=2000)
