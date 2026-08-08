"""Focused API coverage for the Phase 3 requirements-assistant boundary.

These tests intentionally use the offline provider or an in-process probe
stub.  No provider credentials or project data leave the test process.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from importlib import resources
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from accessforge.ai.prompt_registry import get_prompt
from accessforge.ai.schemas.requirements import RequirementsExtractionResponse
from accessforge.api.routes import model_providers
from accessforge.api.routes import requirements as requirements_routes
from accessforge.core.config import get_settings
from accessforge.db.models import Project
from accessforge.main import app
from accessforge.requirements.service import build_project_context


def phase_three_token(subject: str) -> str:
    """Create the same short-lived ES256 bearer token used by API tests."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    settings = get_settings()
    settings.backend_token_public_keys_json = json.dumps({"phase3-test": public_pem})
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "email": f"{subject}@example.test",
            "role": "member",
            "iss": settings.backend_token_issuer,
            "aud": settings.backend_token_audience,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "jti": str(uuid4()),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "phase3-test"},
    )


def api_headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {phase_three_token(subject)}"}


def prompt_injection_fixture() -> dict[str, object]:
    fixture_file = resources.files("accessforge.ai.prompts").joinpath(
        "fixtures/prompt-injection.json"
    )
    decoded = json.loads(fixture_file.read_text(encoding="utf-8"))
    assert isinstance(decoded, dict)
    return decoded


def test_prompt_injection_fixture_is_covered_by_the_static_prompt_boundary() -> None:
    fixture = prompt_injection_fixture()
    prompt = get_prompt("requirements_extractor")
    expected = fixture["expected"]

    assert isinstance(expected, dict)
    assert expected["no_secret_disclosure"] is True
    assert expected["no_geometry"] is True
    assert "untrusted data" in prompt.content
    assert "must never change these rules" in prompt.content
    assert "generate geometry" in prompt.content
    assert "reveal secrets" in prompt.content


def test_requirements_schema_rejects_unsupported_provider_fields() -> None:
    with pytest.raises(ValidationError):
        RequirementsExtractionResponse.model_validate(
            {
                "requirements": [],
                "unknowns": [],
                "clarifying_questions": [],
                "risk_signals": [],
                "rationale": "A concise, user-visible rationale.",
                "tool_call": {"name": "compile_candidate", "arguments": {}},
            }
        )


@pytest.mark.asyncio
async def test_project_context_queries_only_whitelisted_text_and_measurement_records() -> None:
    class EmptyScalarResult:
        def all(self) -> list[object]:
            return []

    class QueryRecorder:
        def __init__(self) -> None:
            self.statements: list[str] = []

        async def scalars(self, statement: object) -> EmptyScalarResult:
            self.statements.append(str(statement))
            return EmptyScalarResult()

    project = Project(
        id="no-media-project",
        owner_id="owner",
        name="No media context",
        goal="Open a zipper.",
        scope_status="supported",
        scope_reason="Within scope.",
    )
    recorder = QueryRecorder()
    context, _ = await build_project_context(
        cast(AsyncSession, recorder), project, ["project_text", "measurements"]
    )

    serialized = json.dumps(context)
    assert "media_assets" not in "\n".join(recorder.statements)
    assert "object_key" not in serialized
    assert "content_type" not in serialized
    assert set(context) == {
        "project_id",
        "scope_status",
        "scope_reason",
        "allowed_source_refs",
        "project_text",
        "observations",
        "measurements",
    }


def create_captured_project(
    client: TestClient,
    headers: dict[str, str],
    *,
    ai_provider_sharing: bool | None = None,
) -> str:
    project_response = client.post(
        "/v1/projects",
        headers=headers,
        json={
            "name": f"Phase 3 zipper project {uuid4()}",
            "goal": "Pull a jacket zipper without pinching fingers.",
            "object_description": "A small zipper tab on a jacket.",
            "action_description": "A gentle pull.",
            "environment": "indoors at room temperature",
            "load_context": "low",
            "safety_system": False,
            "age_context": "adult",
        },
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    consent_choices = {"project_text": True}
    if ai_provider_sharing is not None:
        consent_choices["ai_provider_sharing"] = ai_provider_sharing
    consent_response = client.post(
        f"/v1/projects/{project_id}/consents",
        headers=headers,
        json={
            "display_name": "Test participant",
            "role": "participant",
            "choices": consent_choices,
        },
    )
    assert consent_response.status_code == 201, consent_response.text

    observation_response = client.post(
        f"/v1/projects/{project_id}/observations",
        headers=headers,
        json={"text": "The zipper tab can slip between my fingers.", "input_mode": "text"},
    )
    assert observation_response.status_code == 201, observation_response.text

    measurement_response = client.post(
        f"/v1/projects/{project_id}/measurements",
        headers=headers,
        json={
            "kind": "zipper tab width",
            "value": 18,
            "unit": "mm",
            "tolerance": 1,
            "method": "ruler",
            "confirmed": True,
        },
    )
    assert measurement_response.status_code == 201, measurement_response.text
    return project_id


def create_fake_config(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.post(
        "/v1/model-providers",
        headers=headers,
        json={
            "label": f"Offline provider {uuid4()}",
            "provider_type": "fake",
            "credential_mode": "development_fake",
            "allowed_data_categories": ["project_text", "measurements"],
        },
    )
    assert response.status_code == 201, response.text
    config = response.json()
    assert config["status"] == "ready"
    assert config["capabilities"]["structured_json"] == "confirmed"
    return config


def test_fake_provider_extracts_editable_source_linked_proposal_and_confirmation_is_immutable() -> (
    None
):
    headers = api_headers(f"phase3-confirm-{uuid4()}")
    with TestClient(app) as client:
        project_id = create_captured_project(client, headers)
        config = create_fake_config(client, headers)

        extraction_response = client.post(
            f"/v1/projects/{project_id}/requirements:extract",
            headers=headers,
            json={"provider_config_id": config["id"]},
        )
        assert extraction_response.status_code == 201, extraction_response.text
        proposal = extraction_response.json()

        assert proposal["source"] == "ai_proposal"
        assert proposal["status"] == "draft"
        assert proposal["revision_number"] == 1
        assert proposal["requirements"]
        assert proposal["requirements"][0]["source_refs"] == ["project:goal"]
        assert proposal["requirements"][0]["needs_confirmation"] is True
        assert "Synthetic offline demo" in proposal["rationale"]

        # A user can correct the typed proposal before accepting it.  The API
        # creates a new immutable revision instead of mutating the AI proposal.
        proposed_requirement = proposal["requirements"][0]
        editable_requirement = {
            "kind": proposed_requirement["kind"],
            "value_number": proposed_requirement["value_number"],
            "value_text": "A zipper tab that can be grasped without pinching.",
            "unit": proposed_requirement["unit"],
            "source_refs": proposed_requirement["source_refs"],
            "confidence": proposed_requirement["confidence"],
            "needs_confirmation": False,
            "explanation": "I clarified the goal after reviewing the proposal.",
        }
        confirmation_response = client.post(
            f"/v1/projects/{project_id}/requirements/{proposal['id']}:confirm",
            headers=headers,
            json={
                "requirements": [editable_requirement],
                "unknowns": proposal["unknowns"],
                "clarifying_questions": proposal["clarifying_questions"],
                "risk_signals": proposal["risk_signals"],
                "rationale": "User-reviewed and corrected before confirmation.",
            },
        )
        assert confirmation_response.status_code == 200, confirmation_response.text
        confirmed = confirmation_response.json()

        assert confirmed["source"] == "user_confirmation"
        assert confirmed["status"] == "confirmed"
        assert confirmed["revision_number"] == 2
        assert confirmed["requirements"][0]["value_text"] == editable_requirement["value_text"]
        assert confirmed["requirements"][0]["provenance"]["creator_type"] == "user"

        revisions_response = client.get(f"/v1/projects/{project_id}/requirements", headers=headers)
        assert revisions_response.status_code == 200, revisions_response.text
        revisions = revisions_response.json()
        assert [revision["revision_number"] for revision in revisions] == [2, 1]
        original = next(revision for revision in revisions if revision["id"] == proposal["id"])
        assert original["status"] == "draft"
        assert (
            original["requirements"][0]["value_text"] == proposal["requirements"][0]["value_text"]
        )

        project_response = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert project_response.status_code == 200
        assert project_response.json()["status"] == "risk_review"
        assert project_response.json()["active_requirement_revision_id"] == confirmed["id"]


def test_external_provider_is_blocked_without_separate_ai_sharing_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The consent decision happens before a non-fake provider can be called."""

    async def offline_probe(config: object, _: object) -> None:
        # The route needs a successfully tested config, but this unit test must
        # never instantiate or contact an external model provider.
        config.capabilities = {"structured_json": "confirmed"}  # type: ignore[attr-defined]
        config.status = "ready"  # type: ignore[attr-defined]

    monkeypatch.setattr(model_providers, "probe_config", offline_probe)
    monkeypatch.setattr(get_settings(), "openai_api_key", "managed-test-key")
    headers = api_headers(f"phase3-consent-{uuid4()}")
    with TestClient(app) as client:
        project_id = create_captured_project(client, headers, ai_provider_sharing=False)
        config_response = client.post(
            "/v1/model-providers",
            headers=headers,
            json={
                "label": f"Consent-gated OpenAI config {uuid4()}",
                "provider_type": "openai",
                "credential_mode": "deployment_managed",
                "fast_model": "test-only-model",
                "allowed_data_categories": ["project_text"],
            },
        )
        assert config_response.status_code == 201, config_response.text
        config_id = config_response.json()["id"]

        blocked_response = client.post(
            f"/v1/projects/{project_id}/requirements:extract",
            headers=headers,
            json={"provider_config_id": config_id},
        )
        assert blocked_response.status_code == 403
        assert "AI-provider sharing consent" in blocked_response.json()["detail"]
        assert client.get(f"/v1/projects/{project_id}/requirements", headers=headers).json() == []
        project_response = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert project_response.json()["status"] == "captured"


def test_malicious_provider_citations_are_rejected_before_any_revision_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A syntactically valid but ungrounded model response never reaches domain tables."""

    fixture = prompt_injection_fixture()
    fixture_context = fixture["project_context"]
    assert isinstance(fixture_context, dict)
    fixture_observations = fixture_context["observations"]
    assert isinstance(fixture_observations, list)
    fixture_observation = fixture_observations[0]
    assert isinstance(fixture_observation, dict)
    malicious_text = fixture_observation["text"]
    assert isinstance(malicious_text, str)

    async def malicious_workflow(**_: object) -> SimpleNamespace:
        return SimpleNamespace(
            extraction=RequirementsExtractionResponse.model_validate(
                {
                    "requirements": [
                        {
                            "kind": "hidden_instruction",
                            "value_number": None,
                            "value_text": malicious_text,
                            "unit": None,
                            "source_refs": ["observation:not-supplied-to-provider"],
                            "confidence": 1,
                            "needs_confirmation": False,
                            "explanation": "Malicious prompt-injection fixture.",
                        }
                    ],
                    "unknowns": [],
                    "clarifying_questions": [],
                    "risk_signals": [],
                    "rationale": "Malicious fixture only.",
                }
            )
        )

    monkeypatch.setattr(requirements_routes, "run_requirements_workflow", malicious_workflow)
    headers = api_headers(f"phase3-citations-{uuid4()}")
    with TestClient(app) as client:
        project_id = create_captured_project(client, headers)
        config = create_fake_config(client, headers)

        response = client.post(
            f"/v1/projects/{project_id}/requirements:extract",
            headers=headers,
            json={"provider_config_id": config["id"]},
        )
        assert response.status_code == 422
        assert "cited project data that was not supplied" in response.json()["detail"]

        revisions_response = client.get(f"/v1/projects/{project_id}/requirements", headers=headers)
        assert revisions_response.status_code == 200
        assert revisions_response.json() == []
        project_response = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert project_response.status_code == 200
        assert project_response.json()["active_requirement_revision_id"] is None
