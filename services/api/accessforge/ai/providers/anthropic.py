"""Anthropic Messages API adapter."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import BaseModel

from accessforge.ai.providers.errors import ProviderConfigurationError, ProviderResponseError
from accessforge.ai.providers.http import HTTPModelProvider
from accessforge.ai.providers.models import (
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


class AnthropicProvider(HTTPModelProvider):
    """Official Anthropic Messages adapter with a validated JSON fallback."""

    provider_type = "anthropic"
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

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
        # The adapter intentionally does not expose a general tool loop or raw
        # media path.  JSON is confirmed only after a successful parse probe.
        return ProviderCapabilities(supported_content_types=("text",))

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        return await self._complete(request)

    async def complete_structured[StructuredOutput: BaseModel](
        self,
        request: CompletionRequest,
        schema: type[StructuredOutput],
    ) -> StructuredResult[StructuredOutput]:
        structured = StructuredCompletionRequest(request=request, schema=schema)
        instruction = structured_json_instruction(structured.json_schema)
        with_instruction = request.model_copy(
            update={
                "messages": (
                    *request.messages,
                    # A second system message is normalised into the Anthropic
                    # system field below; user text remains separate data.
                    ChatMessage(role=MessageRole.SYSTEM, content=instruction),
                )
            }
        )
        completion = await self._complete(with_instruction)
        return parse_structured_result(completion, schema)

    async def _complete(self, request: CompletionRequest) -> CompletionResult:
        payload = self._completion_payload(request)
        response, latency_ms = await self._post_json(
            "messages",
            payload,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": self.API_VERSION,
                "content-type": "application/json",
            },
        )
        return self._parse_completion(response, request=request, latency_ms=latency_ms)

    def _completion_payload(self, request: CompletionRequest) -> dict[str, object]:
        system_messages = [
            message.content for message in request.messages if message.role is MessageRole.SYSTEM
        ]
        conversation = [
            {
                "role": "assistant" if message.role is MessageRole.ASSISTANT else "user",
                "content": message.content,
            }
            for message in request.messages
            if message.role is not MessageRole.SYSTEM
        ]
        if not conversation:
            raise ProviderConfigurationError(
                "Anthropic completion requests require at least one user or assistant message."
            )
        payload: dict[str, object] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens or 1024,
            "messages": conversation,
        }
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        return payload

    def _parse_completion(
        self,
        response: Mapping[str, object],
        *,
        request: CompletionRequest,
        latency_ms: int,
    ) -> CompletionResult:
        blocks = as_list(response.get("content"), context="content")
        text_parts: list[str] = []
        for block in blocks:
            item = as_object(block, context="content block")
            if item.get("type") == "text":
                text_parts.append(non_empty_text(item.get("text"), context="text block"))
        if not text_parts:
            raise ProviderResponseError("Anthropic returned no textual completion content.")
        usage = self._parse_usage(response.get("usage"))
        model = optional_text(response.get("model"), context="model") or request.model
        return CompletionResult(
            provider=self.provider_type,
            model=model,
            content="\n".join(text_parts),
            finish_reason=optional_text(response.get("stop_reason"), context="stop reason"),
            usage=usage,
            provider_request_id=optional_text(response.get("id"), context="request ID"),
            latency_ms=latency_ms,
            correlation_id=request.correlation_id,
        )

    def _parse_usage(self, raw_usage: object) -> TokenUsage:
        if raw_usage is None:
            return TokenUsage()
        usage = as_object(raw_usage, context="usage")
        input_tokens = token_count(usage.get("input_tokens"))
        output_tokens = token_count(usage.get("output_tokens"))
        total_tokens = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
