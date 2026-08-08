"""Explicit provider construction without configuration or credential storage."""

from __future__ import annotations

from accessforge.ai.providers.anthropic import AnthropicProvider
from accessforge.ai.providers.deepseek import DeepSeekProvider
from accessforge.ai.providers.errors import ProviderConfigurationError
from accessforge.ai.providers.fake import FakeProvider
from accessforge.ai.providers.google import GoogleProvider
from accessforge.ai.providers.openai import OpenAIProvider
from accessforge.ai.providers.openai_compatible import OpenAICompatibleProvider
from accessforge.ai.providers.protocol import ModelProvider


def build_provider(
    provider_type: str,
    *,
    api_key: str,
    base_url: str | None = None,
    timeout_seconds: float = 30.0,
) -> ModelProvider:
    """Build one supported adapter from an already-authorized credential.

    The caller owns credential retrieval and lifecycle.  This function neither
    persists nor logs the key.  Custom OpenAI-compatible endpoints receive the
    HTTPS-safe default in :class:`OpenAICompatibleProvider`.
    """

    normalised = provider_type.strip().lower().replace("_", "-")
    if normalised == "deepseek":
        return DeepSeekProvider(
            api_key=api_key,
            base_url=base_url or DeepSeekProvider.DEFAULT_BASE_URL,
            timeout_seconds=timeout_seconds,
        )
    if normalised in {"openai-compatible", "openai-compatible-chat"}:
        if base_url is None:
            raise ProviderConfigurationError(
                "A base URL is required for an OpenAI-compatible provider."
            )
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
    if normalised == "openai":
        return OpenAIProvider(
            api_key=api_key,
            base_url=base_url or OpenAIProvider.DEFAULT_BASE_URL,
            timeout_seconds=timeout_seconds,
        )
    if normalised == "anthropic":
        return AnthropicProvider(
            api_key=api_key,
            base_url=base_url or AnthropicProvider.DEFAULT_BASE_URL,
            timeout_seconds=timeout_seconds,
        )
    if normalised in {"google", "gemini", "google-gemini"}:
        return GoogleProvider(
            api_key=api_key,
            base_url=base_url or GoogleProvider.DEFAULT_BASE_URL,
            timeout_seconds=timeout_seconds,
        )
    if normalised in {"fake", "offline-fake"}:
        # The key is accepted for factory uniformity and intentionally ignored.
        return FakeProvider()
    raise ProviderConfigurationError("Unsupported model provider type.")
