"""Sanitised provider errors.

Provider response bodies can contain prompt material, account metadata, or
other sensitive values.  These exceptions intentionally retain only an error
category and a generic message.
"""

from __future__ import annotations


class ModelProviderError(RuntimeError):
    """Base class for safe-to-display provider failures."""

    code = "model_provider_error"


class ProviderConfigurationError(ModelProviderError):
    """The local provider configuration is invalid or unsupported."""

    code = "provider_configuration_error"


class ProviderTransportError(ModelProviderError):
    """A timeout, DNS, or connection failure occurred."""

    code = "provider_transport_error"


class ProviderAuthenticationError(ModelProviderError):
    """A provider rejected a credential without exposing it."""

    code = "provider_authentication_error"


class ProviderRateLimitError(ModelProviderError):
    """A provider rate-limited the request."""

    code = "provider_rate_limit_error"


class ProviderResponseError(ModelProviderError):
    """A provider response was invalid, incomplete, or unsuitable."""

    code = "provider_response_error"


class StructuredOutputError(ModelProviderError):
    """A completion could not be safely parsed against its required schema."""

    code = "structured_output_error"
