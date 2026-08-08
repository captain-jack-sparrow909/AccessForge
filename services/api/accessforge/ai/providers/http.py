"""Shared HTTP safety and low-cost probing for provider adapters."""

from __future__ import annotations

import ipaddress
from abc import ABC, abstractmethod
from collections.abc import Mapping
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict

from accessforge.ai.providers.errors import (
    ModelProviderError,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransportError,
)
from accessforge.ai.providers.models import (
    CapabilityState,
    ChatMessage,
    CompletionRequest,
    MessageRole,
    ProbeStatus,
    ProviderCapabilities,
    ProviderCapabilityProbe,
    StructuredResult,
)

MAX_PROVIDER_RESPONSE_BYTES = 2_000_000


def normalise_base_url(base_url: str, *, allow_unsafe: bool = False) -> str:
    """Validate a provider endpoint before it is handed to HTTPX.

    Hosted custom endpoints must be HTTPS, credential-free, and must not use a
    literal loopback/private address.  DNS allowlisting and re-resolution are
    deployment concerns; this boundary provides a safe default without making
    an unexpected DNS request during construction or tests.
    """

    candidate = base_url.strip()
    if not candidate:
        raise ProviderConfigurationError("A model provider base URL is required.")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProviderConfigurationError("Model provider base URL must be an absolute HTTP(S) URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ProviderConfigurationError("Model provider base URL must not contain credentials.")
    if parsed.query or parsed.fragment:
        raise ProviderConfigurationError(
            "Model provider base URL must not contain a query or fragment."
        )
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ProviderConfigurationError(
            "Model provider base URL contains an invalid port."
        ) from exc
    if not allow_unsafe and parsed.scheme != "https":
        raise ProviderConfigurationError("Custom model provider base URLs must use HTTPS.")

    hostname = parsed.hostname.rstrip(".").lower()
    if not allow_unsafe and (
        hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local")
    ):
        raise ProviderConfigurationError("Custom model provider base URL is not publicly routable.")

    try:
        host_address = ipaddress.ip_address(hostname)
    except ValueError:
        host_address = None
    if (
        host_address is not None
        and not allow_unsafe
        and (
            host_address.is_private
            or host_address.is_loopback
            or host_address.is_link_local
            or host_address.is_multicast
            or host_address.is_reserved
            or host_address.is_unspecified
        )
    ):
        raise ProviderConfigurationError("Custom model provider base URL is not publicly routable.")

    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class _ProbePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool


class HTTPModelProvider(ABC):
    """Base class that never exposes credentials in errors or result models."""

    provider_type = "http"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
        allow_unsafe_base_url: bool = False,
    ) -> None:
        if not api_key.strip():
            raise ProviderConfigurationError("A model provider API key is required.")
        if not 1 <= timeout_seconds <= 120:
            raise ProviderConfigurationError(
                "Model provider timeout must be between 1 and 120 seconds."
            )
        self._api_key = api_key
        self._base_url = normalise_base_url(base_url, allow_unsafe=allow_unsafe_base_url)
        self._timeout_seconds = timeout_seconds
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        """Close only clients created by this adapter."""

        if self._owns_client:
            await self._client.aclose()

    @property
    @abstractmethod
    def advertised_capabilities(self) -> ProviderCapabilities:
        """Return conservative, adapter-level capability states."""

    @abstractmethod
    async def complete_structured[StructuredOutput: BaseModel](
        self,
        request: CompletionRequest,
        schema: type[StructuredOutput],
    ) -> StructuredResult[StructuredOutput]:
        """Return schema-validated output using the provider's best safe mode."""

    async def probe_capabilities(self, model: str | None = None) -> ProviderCapabilityProbe:
        """Probe only when a caller explicitly supplies a model identifier.

        A zero-argument call reports conservative static capabilities.  This
        prevents an unconfigured settings page from spending money or silently
        choosing a provider-specific model.
        """

        capabilities = self.advertised_capabilities
        if model is None:
            return ProviderCapabilityProbe(
                provider=self.provider_type,
                model=None,
                status=ProbeStatus.NOT_RUN,
                capabilities=capabilities,
                message="No model was supplied, so no network capability probe was run.",
            )

        probe_request = CompletionRequest(
            model=model,
            messages=(
                ChatMessage(
                    role=MessageRole.USER,
                    content="Return the requested static probe JSON object.",
                ),
            ),
            temperature=0,
            max_output_tokens=32,
        )
        try:
            await self.complete_structured(probe_request, _ProbePayload)
        except ModelProviderError:
            return ProviderCapabilityProbe(
                provider=self.provider_type,
                model=model,
                status=ProbeStatus.FAILED,
                capabilities=capabilities,
                message="The minimal model capability probe did not complete successfully.",
            )

        confirmed = self._capabilities_after_structured_probe(capabilities)
        return ProviderCapabilityProbe(
            provider=self.provider_type,
            model=model,
            status=ProbeStatus.SUCCEEDED,
            capabilities=confirmed,
            message="The model completed and validated a minimal static structured-output probe.",
        )

    def _capabilities_after_structured_probe(
        self,
        capabilities: ProviderCapabilities,
    ) -> ProviderCapabilities:
        return capabilities.model_copy(update={"structured_json": CapabilityState.CONFIRMED})

    async def _post_json(
        self,
        path: str,
        payload: Mapping[str, object],
        headers: Mapping[str, str],
    ) -> tuple[dict[str, object], int]:
        """Make one bounded request and return only a JSON object."""

        url = f"{self._base_url}/{path.lstrip('/')}"
        started = perf_counter()
        try:
            response = await self._client.post(
                url,
                json=dict(payload),
                headers={"accept": "application/json", **headers},
                follow_redirects=False,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTransportError("Model provider request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderTransportError("Model provider connection failed.") from exc

        latency_ms = max(0, round((perf_counter() - started) * 1000))
        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError("Model provider rejected the credential.")
        if response.status_code == 429:
            raise ProviderRateLimitError("Model provider rate-limited the request.")
        if response.status_code >= 400:
            raise ProviderResponseError(
                f"Model provider rejected the request with status {response.status_code}."
            )
        if len(response.content) > MAX_PROVIDER_RESPONSE_BYTES:
            raise ProviderResponseError("Model provider response exceeded the size limit.")
        try:
            decoded: object = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Model provider did not return JSON.") from exc
        if not isinstance(decoded, Mapping) or not all(isinstance(key, str) for key in decoded):
            raise ProviderResponseError("Model provider returned an invalid JSON response.")
        return {key: value for key, value in decoded.items()}, latency_ms
