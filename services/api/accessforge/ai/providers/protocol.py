"""The small, domain-owned provider protocol.

The protocol intentionally stops before tool loops and agent orchestration.
Those are future workflow responsibilities and must not become an implicit
vendor feature.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from accessforge.ai.providers.models import (
    CompletionRequest,
    CompletionResult,
    ProviderCapabilityProbe,
    StructuredResult,
)


@runtime_checkable
class ModelProvider(Protocol):
    """Vendor-neutral interface used by future requirements workflows."""

    provider_type: str

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Return a text completion with sanitised metadata."""

    async def complete_structured[StructuredOutput: BaseModel](
        self,
        request: CompletionRequest,
        schema: type[StructuredOutput],
    ) -> StructuredResult[StructuredOutput]:
        """Return Pydantic-validated machine-consumable output."""

    async def probe_capabilities(self, model: str | None = None) -> ProviderCapabilityProbe:
        """Run a static or low-cost probe; unknown remains unknown."""
