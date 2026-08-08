"""Vendor-neutral model provider adapters and shared contracts."""

from accessforge.ai.providers.anthropic import AnthropicProvider
from accessforge.ai.providers.deepseek import DeepSeekProvider
from accessforge.ai.providers.errors import (
    ModelProviderError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransportError,
    StructuredOutputError,
)
from accessforge.ai.providers.factory import build_provider
from accessforge.ai.providers.fake import FakeProvider
from accessforge.ai.providers.google import GoogleProvider
from accessforge.ai.providers.models import (
    CapabilityState,
    ChatMessage,
    CompletionRequest,
    CompletionResult,
    MessageRole,
    ProbeStatus,
    ProviderCapabilities,
    ProviderCapabilityProbe,
    StructuredCompletionRequest,
    StructuredResult,
    TokenUsage,
)
from accessforge.ai.providers.openai import OpenAIProvider
from accessforge.ai.providers.openai_compatible import OpenAICompatibleProvider
from accessforge.ai.providers.protocol import ModelProvider

__all__ = [
    "AnthropicProvider",
    "CapabilityState",
    "ChatMessage",
    "CompletionRequest",
    "CompletionResult",
    "DeepSeekProvider",
    "FakeProvider",
    "GoogleProvider",
    "MessageRole",
    "ModelProvider",
    "ModelProviderError",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "ProbeStatus",
    "ProviderAuthenticationError",
    "ProviderCapabilities",
    "ProviderCapabilityProbe",
    "ProviderConfigurationError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTransportError",
    "StructuredCompletionRequest",
    "StructuredOutputError",
    "StructuredResult",
    "TokenUsage",
    "build_provider",
]
