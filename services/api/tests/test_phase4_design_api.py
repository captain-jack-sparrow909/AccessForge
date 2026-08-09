"""API contract tests for the bounded Phase 4 DesignSpec surface.

These tests stay at the authenticated HTTP boundary.  They intentionally use
the development-only offline provider only to reach a confirmed requirements
revision; no external provider, CAD worker, object storage, or physical-output
path is invoked.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from accessforge.core.config import get_settings
from accessforge.main import app


def phase_four_token(subject: str) -> str:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    settings = get_settings()
    settings.backend_token_public_keys_json = json.dumps({"phase4-test": public_pem})
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
        headers={"kid": "phase4-test"},
    )


def api_headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {phase_four_token(subject)}"}


def create_confirmed_project(client: TestClient, headers: dict[str, str]) -> str:
    project_response = client.post(
        "/v1/projects",
        headers=headers,
        json={
            "name": f"Phase 4 pull-tab project {uuid4()}",
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
    project_payload = project_response.json()
    assert isinstance(project_payload, dict)
    project_id = project_payload.get("id")
    assert isinstance(project_id, str)

    consent_response = client.post(
        f"/v1/projects/{project_id}/consents",
        headers=headers,
        json={
            "display_name": "Phase 4 test participant",
            "role": "participant",
            "choices": {"project_text": True},
        },
    )
    assert consent_response.status_code == 201, consent_response.text

    observation_response = client.post(
        f"/v1/projects/{project_id}/observations",
        headers=headers,
        json={"text": "The zipper tab slips between my fingers.", "input_mode": "text"},
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

    provider_response = client.post(
        "/v1/model-providers",
        headers=headers,
        json={
            "label": f"Phase 4 offline provider {uuid4()}",
            "provider_type": "fake",
            "credential_mode": "development_fake",
            "allowed_data_categories": ["project_text", "measurements"],
        },
    )
    assert provider_response.status_code == 201, provider_response.text

    proposal_response = client.post(
        f"/v1/projects/{project_id}/requirements:extract",
        headers=headers,
        json={"provider_config_id": provider_response.json()["id"]},
    )
    assert proposal_response.status_code == 201, proposal_response.text
    proposal = proposal_response.json()

    confirmation_response = client.post(
        f"/v1/projects/{project_id}/requirements/{proposal['id']}:confirm",
        headers=headers,
        json={
            "requirements": [
                {
                    "kind": item["kind"],
                    "value_number": item["value_number"],
                    "value_text": item["value_text"],
                    "unit": item["unit"],
                    "source_refs": item["source_refs"],
                    "confidence": item["confidence"],
                    "needs_confirmation": False,
                    "explanation": item["explanation"],
                }
                for item in proposal["requirements"]
            ],
            "unknowns": proposal["unknowns"],
            "clarifying_questions": proposal["clarifying_questions"],
            "risk_signals": proposal["risk_signals"],
            "rationale": "Confirmed for the Phase 4 deterministic API fixture.",
        },
    )
    assert confirmation_response.status_code == 200, confirmation_response.text
    project_state = client.get(f"/v1/projects/{project_id}", headers=headers)
    assert project_state.status_code == 200, project_state.text
    assert project_state.json()["status"] == "risk_review"
    return project_id


def length(value: float, unit: str = "mm") -> dict[str, object]:
    return {
        "value": value,
        "unit": unit,
        "creator_type": "user",
        "source_ref": "user:phase4-api-fixture",
        "rationale": "Entered explicitly for a synthetic Phase 4 API fixture.",
    }


def pull_tab_design_spec_payload(*, seed: str) -> dict[str, object]:
    return {
        "template_id": "pull_tab_extender",
        "template_version": "1.0.0",
        "parameters": {
            "attachment_slot_width": length(12),
            "attachment_slot_height": length(7),
            "attachment_clearance": length(0.8),
            "pull_loop_outer_width": length(36),
            "pull_loop_outer_height": length(28),
            "body_thickness": length(3.2),
            "edge_radius": length(1.2),
        },
        "manufacturing": {
            "process": "fdm",
            "material_profile": "pla_provisional",
            "nozzle_diameter": length(0.4),
            "layer_height": length(0.2),
            "creator_type": "user",
            "source_ref": "user:phase4-manufacturing",
            "rationale": "A provisional manufacturing profile for a synthetic fixture.",
        },
        "fit_clearance": length(0.4),
        "dimensional_tolerance": length(0.15),
        "uses_assessed": ["Synthetic deterministic CAD API fixture only."],
        "uses_not_assessed": ["Fit, safety, strength, and physical use are not assessed."],
        "confirmed_assumptions": ["This request uses synthetic development data."],
        "unresolved_assumptions": [],
        "generation_seed": seed,
    }


def test_templates_are_public_static_reviewed_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/templates")
        assert response.status_code == 200, response.text
        templates = response.json()
        assert [(item["template_id"], item["version"]) for item in templates] == [
            ("cylindrical_grip_thickener", "1.0.0"),
            ("handle_sleeve", "1.0.0"),
            ("pull_tab_extender", "1.0.0"),
        ]
        assert all(item["status"] == "reviewed_repository_only" for item in templates)
        assert all(len(item["manifest_sha256"]) == 64 for item in templates)

        template_response = client.get("/v1/templates/pull_tab_extender/versions/1.0.0")
        assert template_response.status_code == 200, template_response.text
        template = template_response.json()
        assert template["parameters"]["body_thickness"]["unit"] == "mm"
        assert template["parameters"]["body_thickness"]["minimum"] == 2.4
        assert template["expected_dimensions"]["z"]["source_parameter"] == "body_thickness"

        unknown_response = client.get("/v1/templates/untrusted_template/versions/1.0.0")
        assert unknown_response.status_code == 404


def test_design_specs_are_immutable_versions_with_owned_list_and_get() -> None:
    headers = api_headers(f"phase4-spec-owner-{uuid4()}")
    with TestClient(app) as client:
        project_id = create_confirmed_project(client, headers)
        first_payload = pull_tab_design_spec_payload(seed="phase4-immutable-first")
        first_response = client.post(
            f"/v1/projects/{project_id}/design-specs", headers=headers, json=first_payload
        )
        assert first_response.status_code == 201, first_response.text
        first = first_response.json()
        assert first["revision_number"] == 1
        assert first["generation_seed"] == "phase4-immutable-first"
        assert first["canonical_spec"]["risk_tier"] == "R0"
        assert first["canonical_spec"]["parameters"]["body_thickness"] == {
            "canonical_value_m": 0.0032,
            "canonical_unit": "m",
            "original_value": 3.2,
            "original_unit": "mm",
        }

        second_payload = pull_tab_design_spec_payload(seed="phase4-immutable-second")
        second_payload["parameters"]["body_thickness"] = length(3.6)  # type: ignore[index]
        second_response = client.post(
            f"/v1/projects/{project_id}/design-specs", headers=headers, json=second_payload
        )
        assert second_response.status_code == 201, second_response.text
        second = second_response.json()
        assert second["revision_number"] == 2
        assert second["id"] != first["id"]
        assert second["spec_hash"] != first["spec_hash"]

        first_again = client.get(
            f"/v1/projects/{project_id}/design-specs/{first['id']}", headers=headers
        )
        assert first_again.status_code == 200, first_again.text
        assert first_again.json()["generation_seed"] == "phase4-immutable-first"
        assert (
            first_again.json()["canonical_spec"]["parameters"]["body_thickness"]["original_value"]
            == 3.2
        )

        listed = client.get(f"/v1/projects/{project_id}/design-specs", headers=headers)
        assert listed.status_code == 200, listed.text
        assert [item["id"] for item in listed.json()] == [second["id"], first["id"]]

        other_headers = api_headers(f"phase4-other-owner-{uuid4()}")
        denied = client.get(
            f"/v1/projects/{project_id}/design-specs/{first['id']}", headers=other_headers
        )
        assert denied.status_code == 404


def test_out_of_range_parameter_is_rejected_before_any_design_spec_persists() -> None:
    headers = api_headers(f"phase4-invalid-range-{uuid4()}")
    with TestClient(app) as client:
        project_id = create_confirmed_project(client, headers)
        payload = pull_tab_design_spec_payload(seed="phase4-invalid-range")
        payload["parameters"]["body_thickness"] = length(10.0)  # type: ignore[index]
        response = client.post(
            f"/v1/projects/{project_id}/design-specs", headers=headers, json=payload
        )
        assert response.status_code == 422
        assert "body_thickness must be between 2.4 and 5 mm" in response.json()["detail"]
        assert "never silently clamps" in response.json()["detail"]

        listed = client.get(f"/v1/projects/{project_id}/design-specs", headers=headers)
        assert listed.status_code == 200, listed.text
        assert listed.json() == []


def test_candidate_generation_remains_blocked_before_phase_five_risk_decision() -> None:
    headers = api_headers(f"phase4-generation-gate-{uuid4()}")
    with TestClient(app) as client:
        project_id = create_confirmed_project(client, headers)
        spec_response = client.post(
            f"/v1/projects/{project_id}/design-specs",
            headers=headers,
            json=pull_tab_design_spec_payload(seed="phase4-generation-gate"),
        )
        assert spec_response.status_code == 201, spec_response.text
        spec_id = spec_response.json()["id"]

        generation_response = client.post(
            f"/v1/projects/{project_id}/candidates:generate",
            headers={**headers, "Idempotency-Key": f"phase4-gate-{uuid4()}"},
            json={"design_spec_id": spec_id},
        )
        assert generation_response.status_code == 409
        assert (
            "until Phase 5 records a current deterministic R1 risk decision"
            in (generation_response.json()["detail"])
        )

        candidates = client.get(f"/v1/projects/{project_id}/candidates", headers=headers)
        assert candidates.status_code == 200, candidates.text
        assert candidates.json() == []
        project = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert project.status_code == 200
        assert project.json()["status"] == "risk_review"
