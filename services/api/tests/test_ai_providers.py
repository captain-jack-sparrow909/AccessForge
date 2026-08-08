import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from accessforge.ai.providers import (
    AnthropicProvider,
    CapabilityState,
    ChatMessage,
    CompletionRequest,
    DeepSeekProvider,
    FakeProvider,
    GoogleProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    ProbeStatus,
    ProviderConfigurationError,
    StructuredOutputError,
    build_provider,
)


class ExtractedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    confirmed: bool


def request_for(model: str) -> CompletionRequest:
    return CompletionRequest(
        model=model,
        messages=(ChatMessage(role="user", content="Extract one requirement."),),
        temperature=0,
        max_output_tokens=64,
        correlation_id="provider-contract-test",
    )


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_fake_provider_validates_structured_output_without_recording_prompt() -> None:
    provider = FakeProvider(
        responses=(
            "A plain response.",
            {"kind": "grip_diameter_target", "confirmed": True},
        )
    )

    plain = await provider.complete(request_for("offline"))
    structured = await provider.complete_structured(request_for("offline"), ExtractedRequirement)
    probe = await provider.probe_capabilities()

    assert plain.content == "A plain response."
    assert structured.data.kind == "grip_diameter_target"
    assert structured.completion.correlation_id == "provider-contract-test"
    assert provider.request_count == 2
    assert probe.status is ProbeStatus.SUCCEEDED
    assert probe.capabilities.structured_json is CapabilityState.CONFIRMED
    assert not hasattr(provider, "last_request")


@pytest.mark.asyncio
async def test_structured_parser_rejects_non_json_without_echoing_provider_content() -> None:
    provider = FakeProvider(responses=("sensitive-unstructured-provider-content",))

    with pytest.raises(StructuredOutputError) as error:
        await provider.complete_structured(request_for("offline"), ExtractedRequirement)

    assert "sensitive-unstructured-provider-content" not in str(error.value)


@pytest.mark.asyncio
async def test_openai_uses_native_json_schema_and_normalises_completion() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers.get("authorization")
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "gpt-test",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"kind":"target","confirmed":true}',
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 8,
                    "total_tokens": 12,
                },
            },
        )

    async with client_for(handler) as client:
        provider = OpenAIProvider(api_key="test-only-key", http_client=client)
        result = await provider.complete_structured(request_for("gpt-test"), ExtractedRequirement)

    body = observed["body"]
    assert isinstance(body, dict)
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    assert observed["url"] == "https://api.openai.com/v1/chat/completions"
    assert observed["authorization"] == "Bearer test-only-key"
    assert result.data.confirmed is True
    assert result.completion.usage.total_tokens == 12


@pytest.mark.asyncio
async def test_deepseek_uses_json_mode_and_discards_reasoning_fields() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "deepseek-test",
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"kind":"target","confirmed":true}',
                            "reasoning_content": "this must never leave the adapter",
                        },
                    }
                ],
            },
        )

    async with client_for(handler) as client:
        provider = DeepSeekProvider(api_key="test-only-key", http_client=client)
        result = await provider.complete_structured(
            request_for("deepseek-v4-flash"), ExtractedRequirement
        )

    body = observed["body"]
    assert isinstance(body, dict)
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}
    messages = body["messages"]
    assert isinstance(messages, list)
    assert "reasoning_content" not in result.completion.model_dump_json()


@pytest.mark.asyncio
async def test_openai_compatible_validates_json_without_assuming_native_schema() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "compatible-test",
                "model": "custom-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"kind":"target","confirmed":true}'},
                    }
                ],
            },
        )

    async with client_for(handler) as client:
        provider = OpenAICompatibleProvider(
            api_key="test-only-key",
            base_url="https://compatible.example/v1",
            http_client=client,
        )
        result = await provider.complete_structured(
            request_for("custom-model"), ExtractedRequirement
        )

    body = observed["body"]
    assert isinstance(body, dict)
    assert body["response_format"] == {"type": "json_object"}
    assert result.data == ExtractedRequirement(kind="target", confirmed=True)


@pytest.mark.asyncio
async def test_anthropic_translates_system_and_text_blocks() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["headers"] = dict(request.headers)
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "msg-test",
                "model": "claude-test",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "A response."}],
                "usage": {"input_tokens": 5, "output_tokens": 3},
            },
        )

    request = request_for("claude-test").model_copy(
        update={
            "messages": (
                ChatMessage(role="system", content="Follow the local contract."),
                ChatMessage(role="user", content="Describe the next step."),
            )
        }
    )
    async with client_for(handler) as client:
        provider = AnthropicProvider(api_key="test-only-key", http_client=client)
        result = await provider.complete(request)

    body = observed["body"]
    headers = observed["headers"]
    assert isinstance(body, dict)
    assert isinstance(headers, dict)
    assert body["system"] == "Follow the local contract."
    assert body["messages"] == [{"role": "user", "content": "Describe the next step."}]
    assert headers["x-api-key"] == "test-only-key"
    assert result.usage.total_tokens == 8


@pytest.mark.asyncio
async def test_anthropic_validates_structured_json_fallback() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "anthropic-structured-test",
                "model": "claude-test",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": '{"kind":"target","confirmed":true}'}],
                "usage": {"input_tokens": 2, "output_tokens": 2},
            },
        )

    async with client_for(handler) as client:
        provider = AnthropicProvider(api_key="test-only-key", http_client=client)
        result = await provider.complete_structured(request_for("claude-test"), ExtractedRequirement)

    assert result.data == ExtractedRequirement(kind="target", confirmed=True)


@pytest.mark.asyncio
async def test_google_uses_generation_config_json_schema_and_safe_probe() -> None:
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        observed.append(payload)
        generation_config = payload.get("generationConfig", {})
        is_probe = isinstance(generation_config, dict) and "responseJsonSchema" in generation_config
        response_text = (
            '{"ok":true}'
            if len(observed) == 2 and is_probe
            else ('{"kind":"target","confirmed":true}')
        )
        return httpx.Response(
            200,
            json={
                "responseId": "gemini-test",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": response_text}]},
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 2,
                    "candidatesTokenCount": 4,
                    "totalTokenCount": 6,
                },
            },
        )

    async with client_for(handler) as client:
        provider = GoogleProvider(api_key="test-only-key", http_client=client)
        result = await provider.complete_structured(
            request_for("gemini-test"), ExtractedRequirement
        )
        probe = await provider.probe_capabilities("gemini-test")

    generation_config = observed[0]["generationConfig"]
    assert isinstance(generation_config, dict)
    assert generation_config["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in generation_config
    assert result.completion.usage.total_tokens == 6
    assert probe.status is ProbeStatus.SUCCEEDED
    assert probe.capabilities.native_json_schema is CapabilityState.CONFIRMED


def test_factory_supports_built_ins_and_rejects_unsafe_custom_endpoint() -> None:
    assert build_provider("deepseek", api_key="test-only-key").provider_type == "deepseek"
    assert build_provider("openai", api_key="test-only-key").provider_type == "openai"
    assert build_provider("anthropic", api_key="test-only-key").provider_type == "anthropic"
    assert build_provider("gemini", api_key="test-only-key").provider_type == "google"
    assert build_provider("fake", api_key="ignored").provider_type == "fake"
    with pytest.raises(ProviderConfigurationError):
        build_provider(
            "openai-compatible",
            api_key="test-only-key",
            base_url="http://127.0.0.1:8080/v1",
        )
    with pytest.raises(ProviderConfigurationError):
        build_provider(
            "openai-compatible",
            api_key="test-only-key",
            base_url="https://localhost/v1",
        )
