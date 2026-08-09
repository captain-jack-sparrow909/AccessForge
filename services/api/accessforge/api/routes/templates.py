"""Public metadata for the fixed, repository-reviewed template registry."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from accessforge.cad.registry import (
    TemplateRegistryError,
    TemplateRelease,
    get_template_release,
    list_template_releases,
)

router = APIRouter(prefix="/v1/templates", tags=["templates"])


class TemplateParameterRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    unit: str
    minimum: float
    maximum: float
    default: float
    description: str


class TemplateReleaseRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    version: str
    title: str
    description: str
    manifest_sha256: str
    status: str
    supported_uses: list[str]
    prohibited_uses: list[str]
    parameters: dict[str, TemplateParameterRead]
    expected_dimensions: dict[str, object]
    validation_policy: dict[str, object]
    print_guidance: dict[str, str]
    known_limitations: list[str]


def serialize_template(release: TemplateRelease) -> TemplateReleaseRead:
    manifest = release.manifest
    return TemplateReleaseRead(
        template_id=manifest.template_id,
        version=manifest.version,
        title=manifest.title,
        description=manifest.description,
        manifest_sha256=release.manifest_sha256,
        status=manifest.status,
        supported_uses=list(manifest.supported_uses),
        prohibited_uses=list(manifest.prohibited_uses),
        parameters={
            name: TemplateParameterRead.model_validate(value.model_dump(mode="json"))
            for name, value in manifest.parameters.items()
        },
        expected_dimensions=dict(manifest.expected_dimensions),
        validation_policy=dict(manifest.validation_policy),
        print_guidance=dict(manifest.print_guidance),
        known_limitations=list(manifest.known_limitations),
    )


@router.get("", response_model=list[TemplateReleaseRead])
async def list_templates() -> list[TemplateReleaseRead]:
    return [serialize_template(release) for release in list_template_releases()]


@router.get("/{template_id}/versions/{template_version}", response_model=TemplateReleaseRead)
async def get_template(template_id: str, template_version: str) -> TemplateReleaseRead:
    try:
        return serialize_template(get_template_release(template_id, template_version))
    except TemplateRegistryError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed template release not found."
        ) from exc
