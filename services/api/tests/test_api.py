import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from accessforge.core.config import get_settings
from accessforge.main import app


def test_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_contains_foundation_routes() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    document = response.json()
    assert response.status_code == 200
    assert "/v1/projects" in document["paths"]
    assert "/health/ready" in document["paths"]
    assert "/v1/projects/{project_id}/consents" in document["paths"]
    assert "/v1/projects/{project_id}/measurements" in document["paths"]
    assert "/v1/projects/{project_id}/assets/presign-upload" in document["paths"]
    assert "/v1/model-providers" in document["paths"]
    assert "/v1/projects/{project_id}/requirements:extract" in document["paths"]


def test_project_routes_require_bearer_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/projects")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def phase_two_token(subject: str) -> str:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    settings = get_settings()
    settings.backend_token_public_keys_json = json.dumps({"phase2-test": public_pem})
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
        headers={"kid": "phase2-test"},
    )


def test_phase_two_text_measurement_and_deletion_flow() -> None:
    token = phase_two_token("phase2-owner")
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        project_response = client.post(
            "/v1/projects",
            headers=headers,
            json={
                "name": "Text-only zipper project",
                "goal": "Pull a zipper without pinching.",
                "object_description": "A jacket zipper tab.",
                "action_description": "A gentle pull.",
                "environment": "indoors at room temperature",
                "load_context": "low",
                "safety_system": False,
                "age_context": "adult",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]
        assert project_response.json()["scope_status"] == "supported"

        consent_response = client.post(
            f"/v1/projects/{project_id}/consents",
            headers=headers,
            json={
                "display_name": "Participant",
                "role": "participant",
                "choices": {"project_text": True, "still_images": False, "video": False},
            },
        )
        assert consent_response.status_code == 201
        assert consent_response.json()["project_status"] == "consented"

        upload_response = client.post(
            f"/v1/projects/{project_id}/assets/presign-upload",
            headers=headers,
            json={
                "media_type": "still_image",
                "content_type": "image/png",
                "size_bytes": 128,
                "original_name": "object.png",
            },
        )
        assert upload_response.status_code == 403

        observation_response = client.post(
            f"/v1/projects/{project_id}/observations",
            headers=headers,
            json={"text": "The small tab slips between my fingers.", "input_mode": "text"},
        )
        assert observation_response.status_code == 201
        assert (
            client.get(f"/v1/projects/{project_id}", headers=headers).json()["status"] == "captured"
        )

        measurement_response = client.post(
            f"/v1/projects/{project_id}/measurements",
            headers=headers,
            json={
                "kind": "tab width",
                "value": 1,
                "unit": "in",
                "tolerance": 0.1,
                "method": "ruler",
                "confirmed": True,
            },
        )
        assert measurement_response.status_code == 201
        assert measurement_response.json()["canonical_value_mm"] == 25.4

        delete_response = client.delete(f"/v1/projects/{project_id}", headers=headers)
        assert delete_response.status_code == 202
        assert client.get(f"/v1/projects/{project_id}", headers=headers).status_code == 404
