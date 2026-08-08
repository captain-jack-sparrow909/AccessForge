"""Google Gemini ``generateContent`` API adapter."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from accessforge.ai.providers.errors import ProviderConfigurationError, ProviderResponseError
from accessforge.ai.providers.http import HTTPModelProvider
from accessforge.ai.providers.models import (
    CapabilityState,
    CompletionRequest,
    CompletionResult,
    MessageRole,
    ProviderCapabilities,
    StructuredCompletionRequest,
    StructuredResult,
    TokenUsage,
)
from accessforge.ai.providers.parsing import (
    as_list,
    as_object,
    non_empty_text,
    optional_text,
    parse_structured_result,
    token_count,
)


class GoogleProvider(HTTPModelProvider):
    """Gemini adapter using ``generationConfig.responseJsonSchema``."""

    provider_type = "google"
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

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
        )

    @property
    def advertised_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supported_content_types=("text",))

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        return await self._complete(request, generation_options={})

    async def complete_structured[StructuredOutput: BaseModel](
        self,
        request: CompletionRequest,
        schema: type[StructuredOutput],
    ) -> StructuredResult[StructuredOutput]:
        structured = StructuredCompletionRequest(request=request, schema=schema)
        completion = await self._complete(
            request,
            generation_options={
                "responseMimeType": "application/json",
                "responseJsonSchema": structured.json_schema,
            },
        )
        return parse_structured_result(completion, schema)

    async def _complete(
        self,
        request: CompletionRequest,
        *,
        generation_options: Mapping[str, object],
    ) -> CompletionResult:
        payload = self._completion_payload(request, generation_options=generation_options)
        model_path = quote(request.model, safe="._-")
        if model_path != request.model:
            raise ProviderConfigurationError(
                "Gemini model identifiers contain unsupported characters."
            )
        response, latency_ms = await self._post_json(
            f"models/{model_path}:generateContent",
            payload,
            headers={
                "x-goog-api-key": self._api_key,
                "content-type": "application/json",
            },
        )
        return self._parse_completion(response, request=request, latency_ms=latency_ms)

    def _completion_payload(
        self,
        request: CompletionRequest,
        *,
        generation_options: Mapping[str, object],
    ) -> dict[str, object]:
        system_parts = [
            {"text": message.content}
            for message in request.messages
            if message.role is MessageRole.SYSTEM
        ]
        contents = [
            {
                "role": "model" if message.role is MessageRole.ASSISTANT else "user",
                "parts": [{"text": message.content}],
            }
            for message in request.messages
            if message.role is not MessageRole.SYSTEM
        ]
        if not contents:
            raise ProviderConfigurationError(
                "Gemini completion requests require at least one user or assistant message."
            )
        generation_config: dict[str, object] = dict(generation_options)
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_output_tokens
        payload: dict[str, object] = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        if generation_config:
            payload["generationConfig"] = generation_config
        return payload

    def _parse_completion(
        self,
        response: Mapping[str, object],
        *,
        request: CompletionRequest,
        latency_ms: int,
    ) -> CompletionResult:
        candidates = as_list(response.get("candidates"), context="candidates")
        if not candidates:
            raise ProviderResponseError("Gemini returned no completion candidates.")
        candidate = as_object(candidates[0], context="candidate")
        content = as_object(candidate.get("content"), context="candidate content")
        parts = as_list(content.get("parts"), context="candidate parts")
        text_parts: list[str] = []
        for part in parts:
            item = as_object(part, context="candidate part")
            if "text" in item:
                text_parts.append(non_empty_text(item.get("text"), context="candidate text"))
        if not text_parts:
            raise ProviderResponseError("Gemini returned no textual completion content.")
        return CompletionResult(
            provider=self.provider_type,
            model=request.model,
            content="\n".join(text_parts),
            finish_reason=optional_text(candidate.get("finishReason"), context="finish reason"),
            usage=self._parse_usage(response.get("usageMetadata")),
            provider_request_id=optional_text(response.get("responseId"), context="response ID"),
            latency_ms=latency_ms,
            correlation_id=request.correlation_id,
        )

    def _parse_usage(self, raw_usage: object) -> TokenUsage:
        if raw_usage is None:
            return TokenUsage()
        usage = as_object(raw_usage, context="usage metadata")
        return TokenUsage(
            input_tokens=token_count(usage.get("promptTokenCount")),
            output_tokens=token_count(usage.get("candidatesTokenCount")),
            total_tokens=token_count(usage.get("totalTokenCount")),
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
