"""Offline deterministic provider for local development and contract tests."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable, Mapping

from pydantic import BaseModel

from accessforge.ai.providers.errors import ProviderResponseError
from accessforge.ai.providers.models import (
    CapabilityState,
    CompletionRequest,
    CompletionResult,
    ProbeStatus,
    ProviderCapabilities,
    ProviderCapabilityProbe,
    StructuredResult,
    TokenUsage,
)
from accessforge.ai.providers.parsing import parse_structured_result

FakeResponse = str | Mapping[str, object] | CompletionResult


class FakeProvider:
    """Consume preloaded responses without recording prompts or credentials."""

    provider_type = "fake"

    def __init__(self, responses: Iterable[FakeResponse] = ()) -> None:
        self._responses: deque[FakeResponse] = deque(responses)
        self.request_count = 0

    @property
    def advertised_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            structured_json=CapabilityState.CONFIRMED,
            native_json_schema=CapabilityState.UNSUPPORTED,
            tool_calling=CapabilityState.UNSUPPORTED,
            vision_input=CapabilityState.UNSUPPORTED,
            streaming=CapabilityState.UNSUPPORTED,
            supported_content_types=("text",),
            reasoning_output=CapabilityState.UNSUPPORTED,
        )

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.request_count += 1
        if not self._responses:
            raise ProviderResponseError("Fake provider has no configured response.")
        response = self._responses.popleft()
        if isinstance(response, CompletionResult):
            return response.model_copy(update={"correlation_id": request.correlation_id})
        if isinstance(response, Mapping):
            content = _serialise_mapping(response)
        else:
            content = response
        if not content.strip():
            raise ProviderResponseError("Fake provider response must not be empty.")
        return CompletionResult(
            provider=self.provider_type,
            model=request.model,
            content=content,
            finish_reason="stop",
            usage=TokenUsage(),
            latency_ms=0,
            correlation_id=request.correlation_id,
        )

    async def complete_structured[StructuredOutput: BaseModel](
        self,
        request: CompletionRequest,
        schema: type[StructuredOutput],
    ) -> StructuredResult[StructuredOutput]:
        return parse_structured_result(await self.complete(request), schema)

    async def probe_capabilities(self, model: str | None = None) -> ProviderCapabilityProbe:
        return ProviderCapabilityProbe(
            provider=self.provider_type,
            model=model,
            status=ProbeStatus.SUCCEEDED,
            capabilities=self.advertised_capabilities,
            message="Offline fake provider capability probe succeeded without a network call.",
        )


def _serialise_mapping(value: Mapping[str, object]) -> str:
    """Encode a test-only mapping without accepting arbitrary object values."""

    try:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ProviderResponseError(
            "Fake provider mapping response is not JSON serialisable."
        ) from exc
