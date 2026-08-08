from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.ai.configuration import (
    probe_config,
    store_byok_credential,
    validated_provider_setup,
)
from accessforge.ai.security import CredentialSecurityError
from accessforge.core.config import get_settings
from accessforge.core.security import Principal, get_current_principal
from accessforge.db.models import AuditEvent, ModelProviderConfig, Project, utc_now
from accessforge.db.session import get_session
from accessforge.projects.workflow import ensure_user

router = APIRouter(prefix="/v1/model-providers", tags=["model providers"])

ProviderType = Literal["deepseek", "openai_compatible", "openai", "anthropic", "google", "fake"]
CredentialMode = Literal["byok", "deployment_managed", "development_fake"]


class ModelProviderConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    provider_type: ProviderType
    credential_mode: CredentialMode
    api_key: SecretStr | None = None
    base_url: str | None = Field(default=None, max_length=500)
    fast_model: str | None = Field(default=None, max_length=160)
    reasoning_model: str | None = Field(default=None, max_length=160)
    vision_model: str | None = Field(default=None, max_length=160)
    embedding_model: str | None = Field(default=None, max_length=160)
    input_cost_per_million_usd: float | None = Field(
        default=None, ge=0, le=100_000, allow_inf_nan=False
    )
    output_cost_per_million_usd: float | None = Field(
        default=None, ge=0, le=100_000, allow_inf_nan=False
    )
    allowed_data_categories: list[Literal["project_text", "measurements"]] = Field(min_length=1)


class ModelProviderConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    provider_type: str
    credential_mode: str
    credential_fingerprint: str | None
    base_url: str | None
    fast_model: str | None
    reasoning_model: str | None
    vision_model: str | None
    embedding_model: str | None
    input_cost_per_million_usd: float | None
    output_cost_per_million_usd: float | None
    allowed_data_categories: list[str]
    capabilities: dict[str, object] | None
    capabilities_checked_at: datetime | None
    last_tested_at: datetime | None
    last_error_code: str | None
    status: str
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


async def get_owned_config(
    session: AsyncSession, principal: Principal, config_id: str, *, include_revoked: bool = False
) -> ModelProviderConfig:
    config = await session.scalar(
        select(ModelProviderConfig).where(
            ModelProviderConfig.id == config_id, ModelProviderConfig.owner_id == principal.subject
        )
    )
    if config is None or (config.status == "revoked" and not include_revoked):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model configuration not found."
        )
    return config


@router.get("", response_model=list[ModelProviderConfigRead])
async def list_model_providers(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ModelProviderConfig]:
    result = await session.scalars(
        select(ModelProviderConfig)
        .where(
            ModelProviderConfig.owner_id == principal.subject,
            ModelProviderConfig.status != "revoked",
        )
        .order_by(ModelProviderConfig.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=ModelProviderConfigRead, status_code=status.HTTP_201_CREATED)
async def create_model_provider(
    payload: ModelProviderConfigCreate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ModelProviderConfig:
    settings = get_settings()
    try:
        setup = validated_provider_setup(
            provider_type=payload.provider_type,
            credential_mode=payload.credential_mode,
            base_url=payload.base_url,
            fast_model=payload.fast_model,
            reasoning_model=payload.reasoning_model,
            vision_model=payload.vision_model,
            embedding_model=payload.embedding_model,
            allowed_data_categories=payload.allowed_data_categories,
            settings=settings,
        )
    except (CredentialSecurityError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if setup.credential_mode == "byok" and payload.api_key is None:
        raise HTTPException(
            status_code=422, detail="An API key is required for bring-your-own-key."
        )
    await ensure_user(session, principal)
    config = ModelProviderConfig(
        owner_id=principal.subject,
        label=payload.label.strip(),
        provider_type=setup.provider_type,
        credential_mode=setup.credential_mode,
        base_url=setup.base_url,
        fast_model=setup.fast_model,
        reasoning_model=setup.reasoning_model,
        vision_model=setup.vision_model,
        embedding_model=setup.embedding_model,
        input_cost_per_million_usd=payload.input_cost_per_million_usd,
        output_cost_per_million_usd=payload.output_cost_per_million_usd,
        allowed_data_categories=setup.allowed_data_categories,
    )
    session.add(config)
    await session.flush()
    if setup.credential_mode == "byok":
        assert payload.api_key is not None
        try:
            store_byok_credential(config, payload.api_key.get_secret_value(), settings)
        except CredentialSecurityError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    await probe_config(config, settings)
    await session.commit()
    await session.refresh(config)
    return config


@router.post("/{config_id}:test", response_model=ModelProviderConfigRead)
async def test_model_provider(
    config_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> ModelProviderConfig:
    config = await get_owned_config(session, principal, config_id)
    await probe_config(config, get_settings())
    config.updated_at = utc_now()
    config.version += 1
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/{config_id}")
async def revoke_model_provider(
    config_id: str,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    config = await get_owned_config(session, principal, config_id)
    config.encrypted_credential = None
    config.credential_fingerprint = None
    config.status = "revoked"
    config.revoked_at = utc_now()
    config.updated_at = utc_now()
    config.version += 1
    projects = list(
        (
            await session.scalars(
                select(Project).where(
                    Project.owner_id == principal.subject,
                    Project.model_provider_config_id == config.id,
                )
            )
        ).all()
    )
    for project in projects:
        project.model_provider_config_id = None
        project.version += 1
        session.add(
            AuditEvent(
                project_id=project.id,
                actor_id=principal.subject,
                event_type="model_provider.revoked",
                reason="User revoked the selected model provider configuration.",
                details={"provider_config_id": config.id},
            )
        )
    await session.commit()
    return {"id": config.id, "status": "revoked"}
