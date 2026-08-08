"""OpenAI Chat Completions-compatible provider adapter."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import BaseModel

from accessforge.ai.providers.errors import ProviderResponseError
from accessforge.ai.providers.http import HTTPModelProvider
from accessforge.ai.providers.models import (
    CapabilityState,
    ChatMessage,
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
    structured_json_instruction,
    token_count,
)


class OpenAICompatibleProvider(HTTPModelProvider):
    """Adapter for a configured Chat Completions-compatible HTTPS endpoint."""

    provider_type = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
        allow_unsafe_base_url: bool = False,
        provider_type: str | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
            allow_unsafe_base_url=allow_unsafe_base_url,
        )
        if provider_type is not None:
            self.provider_type = provider_type

    @property
    def advertised_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            tool_calling=CapabilityState.UNKNOWN,
            vision_input=CapabilityState.UNKNOWN,
            streaming=CapabilityState.UNSUPPORTED,
            supported_content_types=("text",),
            reasoning_output=CapabilityState.UNKNOWN,
        )

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        return await self._complete_with_options(request, extra_payload={})

    async def complete_structured[StructuredOutput: BaseModel](
        self,
        request: CompletionRequest,
        schema: type[StructuredOutput],
    ) -> StructuredResult[StructuredOutput]:
        structured = StructuredCompletionRequest(request=request, schema=schema)
        request_with_instruction = self._with_json_instruction(structured)
        completion = await self._complete_with_options(
            request_with_instruction,
            extra_payload={"response_format": {"type": "json_object"}},
        )
        return parse_structured_result(completion, schema)

    def _with_json_instruction[StructuredOutput: BaseModel](
        self,
        structured: StructuredCompletionRequest[StructuredOutput],
    ) -> CompletionRequest:
        instruction = structured_json_instruction(structured.json_schema)
        return structured.request.model_copy(
            update={
                "messages": (
                    ChatMessage(role=MessageRole.SYSTEM, content=instruction),
                    *structured.request.messages,
                )
            }
        )

    async def _complete_with_options(
        self,
        request: CompletionRequest,
        *,
        extra_payload: Mapping[str, object],
    ) -> CompletionResult:
        payload = self._completion_payload(request)
        payload.update(extra_payload)
        response, latency_ms = await self._post_json(
            "chat/completions",
            payload,
            headers={
                "authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            },
        )
        return self._parse_completion(response, request=request, latency_ms=latency_ms)

    def _completion_payload(self, request: CompletionRequest) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": request.model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload[self._max_output_tokens_field] = request.max_output_tokens
        return payload

    @property
    def _max_output_tokens_field(self) -> str:
        return "max_tokens"

    def _parse_completion(
        self,
        response: Mapping[str, object],
        *,
        request: CompletionRequest,
        latency_ms: int,
    ) -> CompletionResult:
        choices = as_list(response.get("choices"), context="choices")
        if not choices:
            raise ProviderResponseError("Model provider returned no completion choices.")
        choice = as_object(choices[0], context="completion choice")
        message = as_object(choice.get("message"), context="completion message")
        content = non_empty_text(message.get("content"), context="completion content")
        finish_reason = optional_text(choice.get("finish_reason"), context="finish reason")
        usage = self._parse_usage(response.get("usage"))
        model = optional_text(response.get("model"), context="model") or request.model
        provider_request_id = optional_text(response.get("id"), context="request ID")
        return CompletionResult(
            provider=self.provider_type,
            model=model,
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            provider_request_id=provider_request_id,
            latency_ms=latency_ms,
            correlation_id=request.correlation_id,
        )

    def _parse_usage(self, raw_usage: object) -> TokenUsage:
        if raw_usage is None:
            return TokenUsage()
        usage = as_object(raw_usage, context="usage")
        return TokenUsage(
            input_tokens=token_count(usage.get("prompt_tokens")),
            output_tokens=token_count(usage.get("completion_tokens")),
            total_tokens=token_count(usage.get("total_tokens")),
        )
