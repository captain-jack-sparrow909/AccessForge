"""OpenAI Chat Completions adapter with native JSON Schema output."""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from accessforge.ai.providers.models import (
    CapabilityState,
    CompletionRequest,
    ProviderCapabilities,
    StructuredCompletionRequest,
    StructuredResult,
)
from accessforge.ai.providers.openai_compatible import OpenAICompatibleProvider
from accessforge.ai.providers.parsing import parse_structured_result


class OpenAIProvider(OpenAICompatibleProvider):
    """Official OpenAI adapter using ``response_format.json_schema``."""

    provider_type = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
            provider_type=self.provider_type,
        )

    @property
    def _max_output_tokens_field(self) -> str:
        return "max_completion_tokens"

    async def complete_structured[StructuredOutput: BaseModel](
        self,
        request: CompletionRequest,
        schema: type[StructuredOutput],
    ) -> StructuredResult[StructuredOutput]:
        structured = StructuredCompletionRequest(request=request, schema=schema)
        completion = await self._complete_with_options(
            request,
            extra_payload={
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": structured.output_name,
                        "schema": structured.json_schema,
                        "strict": False,
                    },
                }
            },
        )
        return parse_structured_result(completion, schema)

    @property
    def advertised_capabilities(self) -> ProviderCapabilities:
        return super().advertised_capabilities.model_copy(
            update={"native_json_schema": CapabilityState.UNKNOWN}
        )

    def _capabilities_after_structured_probe(
        self,
        capabilities: ProviderCapabilities,
    ) -> ProviderCapabilities:
        return capabilities.model_copy(
            update={
                "structured_json": CapabilityState.CONFIRMED,
                "native_json_schema": CapabilityState.CONFIRMED,
            }
        )
