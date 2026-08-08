"""Typed, vendor-neutral contracts for model providers.

Only text messages are accepted at this boundary.  Raw project media must be
handled by a separately consented, capability-gated workflow before it ever
reaches a provider adapter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageRole(StrEnum):
    """Text-chat roles shared across the supported APIs."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """One bounded text message supplied to a model provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: MessageRole
    content: str = Field(min_length=1, max_length=200_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message content must not be blank.")
        return value


class CompletionRequest(BaseModel):
    """A vendor-neutral, text-only completion request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1, max_length=200)
    messages: tuple[ChatMessage, ...] = Field(min_length=1, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1, le=32_768)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("model", "correlation_id")
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\r\n\x00"):
            raise ValueError("Value must not contain control characters.")
        return value


class TokenUsage(BaseModel):
    """Normalised token accounting when a provider returns it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class CompletionResult(BaseModel):
    """Sanitised provider result without raw responses or reasoning traces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=1_000_000)
    finish_reason: str | None = Field(default=None, max_length=100)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    provider_request_id: str | None = Field(default=None, max_length=256)
    latency_ms: int = Field(ge=0)
    correlation_id: str | None = Field(default=None, max_length=128)


@dataclass(frozen=True, slots=True)
class StructuredCompletionRequest[StructuredOutput: BaseModel]:
    """A completion request paired with its Pydantic output contract.

    The schema class is deliberately not serialisable.  It is a local code
    contract, never provider-supplied or persisted as untrusted data.
    """

    request: CompletionRequest
    schema: type[StructuredOutput]
    schema_name: str | None = None

    @property
    def output_name(self) -> str:
        """Return a stable identifier accepted by JSON-schema API variants."""

        candidate = self.schema_name or self.schema.__name__
        normalised = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate).strip("_")
        return (normalised or "structured_output")[:64]

    @property
    def json_schema(self) -> dict[str, object]:
        document: object = self.schema.model_json_schema()
        if not isinstance(document, dict) or not all(isinstance(key, str) for key in document):
            raise TypeError("Pydantic model JSON schema must be an object with string keys.")
        return {key: value for key, value in document.items()}


@dataclass(frozen=True, slots=True)
class StructuredResult[StructuredOutput: BaseModel]:
    """A validated structured result and the metadata of its completion."""

    data: StructuredOutput
    completion: CompletionResult


class CapabilityState(StrEnum):
    """A conservative capability state shown to downstream workflows."""

    CONFIRMED = "confirmed"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class ProbeStatus(StrEnum):
    """Whether a low-cost, static probe was run successfully."""

    NOT_RUN = "not_run"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


ContentType = Literal["text", "image", "audio", "video"]


class ProviderCapabilities(BaseModel):
    """Capability states rather than optimistic vendor-name assumptions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    structured_json: CapabilityState = CapabilityState.UNKNOWN
    native_json_schema: CapabilityState = CapabilityState.UNKNOWN
    tool_calling: CapabilityState = CapabilityState.UNKNOWN
    vision_input: CapabilityState = CapabilityState.UNKNOWN
    streaming: CapabilityState = CapabilityState.UNSUPPORTED
    max_context_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    supported_content_types: tuple[ContentType, ...] = ("text",)
    reasoning_output: CapabilityState = CapabilityState.UNKNOWN

    def is_confirmed(
        self,
        capability: Literal[
            "structured_json",
            "native_json_schema",
            "tool_calling",
            "vision_input",
            "streaming",
            "reasoning_output",
        ],
    ) -> bool:
        return getattr(self, capability) is CapabilityState.CONFIRMED


class ProviderCapabilityProbe(BaseModel):
    """A safe probe record suitable for later persistence by a domain service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1, max_length=64)
    model: str | None = Field(default=None, max_length=200)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: ProbeStatus
    capabilities: ProviderCapabilities
    message: str = Field(min_length=1, max_length=500)
