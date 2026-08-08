"""Provider-configuration lifecycle without secret persistence in callers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from accessforge.ai.providers import ModelProvider, ModelProviderError, build_provider
from accessforge.ai.security import (
    CredentialKeyError,
    decrypt_credential,
    encrypt_credential,
    validate_custom_base_url,
)
from accessforge.core.config import Settings
from accessforge.db.models import ModelProviderConfig

ProviderType = Literal["deepseek", "openai_compatible", "openai", "anthropic", "google", "fake"]
CredentialMode = Literal["byok", "deployment_managed", "development_fake"]
ALLOWED_PROVIDER_TYPES = frozenset(
    {"deepseek", "openai_compatible", "openai", "anthropic", "google", "fake"}
)
ALLOWED_CREDENTIAL_MODES = frozenset({"byok", "deployment_managed", "development_fake"})
ALLOWED_DATA_CATEGORIES = frozenset({"project_text", "measurements"})


@dataclass(frozen=True)
class ProviderSetup:
    provider_type: ProviderType
    credential_mode: CredentialMode
    base_url: str | None
    fast_model: str
    reasoning_model: str | None
    vision_model: str | None
    embedding_model: str | None
    allowed_data_categories: list[str]


def validated_provider_setup(
    *,
    provider_type: str,
    credential_mode: str,
    base_url: str | None,
    fast_model: str | None,
    reasoning_model: str | None,
    vision_model: str | None,
    embedding_model: str | None,
    allowed_data_categories: Iterable[str],
    settings: Settings,
) -> ProviderSetup:
    normalized_type = provider_type.strip().lower()
    normalized_mode = credential_mode.strip().lower()
    if normalized_type not in ALLOWED_PROVIDER_TYPES:
        raise ValueError("Unsupported model provider type.")
    if normalized_mode not in ALLOWED_CREDENTIAL_MODES:
        raise ValueError("Unsupported credential mode.")
    if normalized_type == "fake":
        if settings.app_env != "development" or normalized_mode != "development_fake":
            raise ValueError("The offline fake provider is available only in local development.")
    elif normalized_mode == "development_fake":
        raise ValueError("Development fake credentials can be used only with the fake provider.")
    elif normalized_mode == "deployment_managed" and not settings.managed_provider_key(
        normalized_type
    ):
        raise ValueError("This deployment does not have a managed key for the selected provider.")
    categories = list(dict.fromkeys(category.strip() for category in allowed_data_categories))
    if not categories or not set(categories).issubset(ALLOWED_DATA_CATEGORIES):
        raise ValueError("Choose one or more supported project data categories.")
    normalized_base_url: str | None = None
    if normalized_type == "openai_compatible":
        if not base_url:
            raise ValueError("A custom OpenAI-compatible endpoint is required.")
        normalized_base_url = validate_custom_base_url(
            base_url,
            allow_unsafe_self_hosted=settings.allow_unsafe_custom_model_endpoints,
            allowlist=settings.custom_model_endpoint_allowlist_values or None,
        )
    elif base_url:
        raise ValueError(
            "Custom base URLs are supported only for OpenAI-compatible configurations."
        )
    default_fast_model = default_model_for(normalized_type, settings)
    selected_fast_model = (fast_model or default_fast_model or "").strip()
    if not selected_fast_model:
        raise ValueError("A fast extraction model is required for this provider.")
    return ProviderSetup(
        provider_type=normalized_type,  # type: ignore[arg-type]
        credential_mode=normalized_mode,  # type: ignore[arg-type]
        base_url=normalized_base_url,
        fast_model=selected_fast_model,
        reasoning_model=(
            clean_model_name(reasoning_model)
            or default_reasoning_model_for(normalized_type, settings)
        ),
        vision_model=clean_model_name(vision_model),
        embedding_model=clean_model_name(embedding_model),
        allowed_data_categories=categories,
    )


def default_model_for(provider_type: str, settings: Settings) -> str | None:
    return {
        "deepseek": settings.deepseek_fast_model,
        "openai": settings.openai_fast_model,
        "anthropic": settings.anthropic_fast_model,
        "google": settings.google_fast_model,
        "fake": "accessforge-offline-fake-v1",
    }.get(provider_type)


def default_reasoning_model_for(provider_type: str, settings: Settings) -> str | None:
    return {
        "deepseek": settings.deepseek_reasoning_model,
        "openai": settings.openai_reasoning_model,
        "anthropic": settings.anthropic_reasoning_model,
        "google": settings.google_reasoning_model,
    }.get(provider_type)


def clean_model_name(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > 160 or any(character in trimmed for character in "\r\n\x00"):
        raise ValueError("Model identifiers contain invalid characters.")
    return trimmed


def store_byok_credential(config: ModelProviderConfig, plaintext: str, settings: Settings) -> None:
    if not settings.model_credential_encryption_key:
        raise CredentialKeyError(
            "MODEL_CREDENTIAL_ENCRYPTION_KEY is required before storing a personal provider key."
        )
    config.encrypted_credential = encrypt_credential(
        plaintext,
        settings.model_credential_encryption_key,
        config.owner_id,
        config.id,
    )
    from accessforge.ai.security import credential_fingerprint

    config.credential_fingerprint = credential_fingerprint(plaintext)


def credential_for_config(config: ModelProviderConfig, settings: Settings) -> str:
    if config.credential_mode == "development_fake":
        return "development-fake"
    if config.credential_mode == "deployment_managed":
        credential = settings.managed_provider_key(config.provider_type)
        if not credential:
            raise ValueError("The deployment-managed provider key is unavailable.")
        return credential
    if config.credential_mode == "byok":
        if not settings.model_credential_encryption_key or not config.encrypted_credential:
            raise ValueError("The encrypted provider credential is unavailable.")
        return decrypt_credential(
            config.encrypted_credential,
            settings.model_credential_encryption_key,
            config.owner_id,
            config.id,
        )
    raise ValueError("The provider configuration has an unsupported credential mode.")


def effective_base_url(config: ModelProviderConfig, settings: Settings) -> str | None:
    """Select deployment-owned vendor endpoints without exposing them in the UI."""

    if config.base_url:
        return config.base_url
    return {
        "deepseek": settings.deepseek_api_base,
        "openai": settings.openai_api_base,
    }.get(config.provider_type)


def build_configured_provider(config: ModelProviderConfig, settings: Settings) -> ModelProvider:
    if config.provider_type == "openai_compatible" and config.base_url:
        # Revalidate immediately before an outbound connection to detect DNS rebinding.
        validate_custom_base_url(
            config.base_url,
            allow_unsafe_self_hosted=settings.allow_unsafe_custom_model_endpoints,
            allowlist=settings.custom_model_endpoint_allowlist_values or None,
        )
    return build_provider(
        config.provider_type,
        api_key=credential_for_config(config, settings),
        base_url=effective_base_url(config, settings),
        timeout_seconds=settings.model_provider_timeout_seconds,
    )


async def probe_config(config: ModelProviderConfig, settings: Settings) -> None:
    """Persist only capability metadata and safe error categories after a probe."""
    provider: ModelProvider | None = None
    try:
        provider = build_configured_provider(config, settings)
        probe = await provider.probe_capabilities(model=config.fast_model)
        config.capabilities = probe.capabilities.model_dump(mode="json")
        config.capabilities_checked_at = probe.checked_at
        config.last_tested_at = datetime.now(UTC)
        config.last_error_code = None if probe.status.value == "succeeded" else "probe_failed"
        config.status = "ready" if probe.status.value == "succeeded" else "unverified"
    except ModelProviderError as exc:
        config.last_tested_at = datetime.now(UTC)
        config.last_error_code = exc.code
        config.status = "failed"
    except (CredentialKeyError, ValueError):
        config.last_tested_at = datetime.now(UTC)
        config.last_error_code = "configuration_error"
        config.status = "failed"
    finally:
        if provider is not None:
            close = getattr(provider, "aclose", None)
            if close is not None:
                await close()
