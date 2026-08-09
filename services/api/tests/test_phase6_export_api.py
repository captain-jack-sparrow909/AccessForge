"""HTTP regression coverage for the fail-closed Phase 6 boundary.

The fixtures intentionally stop at a queued, synthetic software candidate.  They
do not compile artifacts, enable a gate, create bundle bytes, or make any
physical-use conclusion.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_phase4_design_api import (
    api_headers,
    create_confirmed_project,
    pull_tab_design_spec_payload,
)

from accessforge.db.models import (
    ApprovalEvent,
    CandidateDesign,
    CandidateGenerationBatch,
    CandidateValidationRun,
    ExportBundle,
    ExportValidationRun,
    Project,
    RiskAssessment,
)
from accessforge.db.session import session_factory
from accessforge.main import app


def _synthetic_r1_risk_payload(design_spec_id: str) -> dict[str, str]:
    return {
        "design_spec_id": design_spec_id,
        "intended_use": (
            "Synthetic HTTP test input only: a passive room-temperature pull-tab "
            "extension for a jacket zipper during a low-energy occasional pull."
        ),
        "body_contact": "incidental",
        "load": "low_energy_occasional",
        "temperature": "room_temperature",
        "chemicals": "none",
        "electricity": "none",
        "age_group": "adult",
        "safety_feature_interaction": "none",
        "failure_consequence": "minor_inconvenience",
        "duration": "occasional",
        "fatigue": "not_expected",
        "manufacturing_uncertainty": "bounded",
    }


def _queue_synthetic_candidate(
    client: TestClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str]:
    """Create a real HTTP candidate path while keeping CAD work out of this test."""

    monkeypatch.setattr("accessforge.api.routes.risk.compile_cad_candidate.delay", lambda _: None)
    project_id = create_confirmed_project(client, headers)
    source_spec_response = client.post(
        f"/v1/projects/{project_id}/design-specs",
        headers=headers,
        json=pull_tab_design_spec_payload(seed=f"phase6-http-{uuid4()}"),
    )
    assert source_spec_response.status_code == 201, source_spec_response.text

    assessment_response = client.post(
        f"/v1/projects/{project_id}/risk:assess",
        headers=headers,
        json=_synthetic_r1_risk_payload(source_spec_response.json()["id"]),
    )
    assert assessment_response.status_code == 201, assessment_response.text
    assert assessment_response.json()["tier"] == "R1"

    plan_response = client.post(
        f"/v1/projects/{project_id}/design-plans",
        headers=headers,
        json={"risk_assessment_id": assessment_response.json()["id"]},
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()

    batch_response = client.post(
        f"/v1/projects/{project_id}/design-plans/{plan['id']}:generate-comparison",
        headers={**headers, "Idempotency-Key": f"phase6-queued-{uuid4()}"},
    )
    assert batch_response.status_code == 202, batch_response.text
    batch = batch_response.json()
    assert batch["status"] == "queued"
    assert batch["candidates"]
    return project_id, batch["candidates"][0]["id"]


def _acknowledgement_payload() -> dict[str, object]:
    return {
        "acknowledgement_version": "phase6-controlled-export.v1",
        "acknowledgements": {
            "exact_revision_reviewed": True,
            "limitations_understood": True,
            "non_human_controlled_validation_only": True,
        },
    }


async def _set_user_review_fixture(project_id: str) -> None:
    """Arrange a test-only review boundary without compiling an artifact."""

    async with session_factory() as session:
        project = await session.get(Project, project_id)
        assert project is not None
        assert project.active_risk_assessment_id is not None
        project.status = "user_review"
        await session.commit()


async def _seed_synthetic_export_metadata(
    project_id: str,
    candidate_id: str,
    *,
    approval_status: str,
    bundle_status: str,
) -> tuple[str, str]:
    """Insert relational metadata only; no bundle bytes, storage, or gate is used."""

    now = datetime.now(UTC)
    async with session_factory() as session:
        project = await session.get(Project, project_id)
        candidate = await session.get(CandidateDesign, candidate_id)
        assert project is not None
        assert candidate is not None
        assert candidate.risk_assessment_id is not None
        assert candidate.generation_batch_id is not None
        assessment = await session.get(RiskAssessment, candidate.risk_assessment_id)
        batch = await session.get(CandidateGenerationBatch, candidate.generation_batch_id)
        assert assessment is not None
        assert batch is not None

        candidate_validation = CandidateValidationRun(
            project_id=project.id,
            candidate_id=candidate.id,
            risk_assessment_id=assessment.id,
            design_spec_id=candidate.design_spec_id,
            validator_version="phase6-synthetic-fixture",
            validator_hash="1" * 64,
            input_hash="2" * 64,
            overall_status="passed",
            report={"overall_status": "passed", "synthetic": True},
            report_hash="3" * 64,
        )
        session.add(candidate_validation)
        await session.flush()
        export_validation = ExportValidationRun(
            project_id=project.id,
            candidate_id=candidate.id,
            risk_assessment_id=assessment.id,
            design_spec_id=candidate.design_spec_id,
            validation_run_id=candidate_validation.id,
            boundary="synthetic-test",
            risk_input_hash="4" * 64,
            risk_decision_hash="5" * 64,
            validation_report_hash="3" * 64,
            artifact_manifest={"synthetic": True},
            artifact_manifest_hash="6" * 64,
            status="synthetic",
            reasons=["Synthetic test metadata only."],
        )
        session.add(export_validation)
        await session.flush()
        approval = ApprovalEvent(
            project_id=project.id,
            candidate_id=candidate.id,
            design_plan_id=batch.design_plan_id,
            generation_batch_id=batch.id,
            requirements_revision_id=assessment.requirements_revision_id,
            risk_assessment_id=assessment.id,
            design_spec_id=candidate.design_spec_id,
            export_validation_run_id=export_validation.id,
            idempotency_key=f"phase6-synthetic-approval-{uuid4()}",
            acknowledgement_version="phase6-controlled-export.v1",
            acknowledgements=_acknowledgement_payload()["acknowledgements"],
            risk_decision_hash="5" * 64,
            design_spec_hash=candidate.spec_hash,
            template_manifest_sha256=candidate.template_manifest_sha256,
            validation_report_hash="3" * 64,
            artifact_manifest_hash="6" * 64,
            approval_hash="7" * 64,
            status=approval_status,
            approved_by="phase6-synthetic-fixture",
            invalidated_at=now if approval_status == "invalidated" else None,
            invalidated_reason=(
                "Synthetic invalidation fixture." if approval_status == "invalidated" else None
            ),
        )
        session.add(approval)
        await session.flush()
        bundle = ExportBundle(
            project_id=project.id,
            candidate_id=candidate.id,
            approval_event_id=approval.id,
            export_validation_run_id=export_validation.id,
            idempotency_key=f"phase6-synthetic-bundle-{uuid4()}",
            status=bundle_status,
            filename="synthetic-metadata-only.zip",
            object_key=f"synthetic/phase6/{uuid4()}.zip",
            checksum_sha256="8" * 64,
            size_bytes=0,
            manifest={"synthetic": True},
            manifest_hash="9" * 64,
            revoked_at=now if bundle_status == "revoked" else None,
            revoked_reason=(
                "Synthetic revocation fixture." if bundle_status == "revoked" else None
            ),
        )
        session.add(bundle)
        await session.commit()
        return approval.id, bundle.id


async def _authorization_statuses(approval_id: str, bundle_id: str) -> tuple[str, str]:
    async with session_factory() as session:
        approval = await session.get(ApprovalEvent, approval_id)
        bundle = await session.get(ExportBundle, bundle_id)
        assert approval is not None
        assert bundle is not None
        return approval.status, bundle.status


def test_queued_http_candidate_is_default_denied_at_readiness_and_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_headers = api_headers(f"phase6-default-deny-{uuid4()}")
    with TestClient(app) as client:
        project_id, candidate_id = _queue_synthetic_candidate(client, owner_headers, monkeypatch)
        readiness_response = client.get(
            f"/v1/projects/{project_id}/candidates/{candidate_id}/export-readiness",
            headers=owner_headers,
        )
        assert readiness_response.status_code == 200, readiness_response.text
        readiness = readiness_response.json()
        assert readiness["allowed"] is False
        assert readiness["reasons"]
        assert readiness["artifact_manifest"]["candidate_id"] == candidate_id
        assert "not a safety result" in readiness["limitations"]

        denied_approval = client.post(
            f"/v1/projects/{project_id}/candidates/{candidate_id}:approve-export",
            headers={**owner_headers, "Idempotency-Key": f"phase6-denied-{uuid4()}"},
            json=_acknowledgement_payload(),
        )
        assert denied_approval.status_code == 409, denied_approval.text
        assert denied_approval.headers["content-type"].startswith("application/problem+json")


def test_feedback_and_hazard_routes_enforce_ownership_and_hazard_invalidates_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_headers = api_headers(f"phase6-feedback-owner-{uuid4()}")
    other_headers = api_headers(f"phase6-feedback-other-{uuid4()}")
    feedback_payload = {
        "category": "fit",
        "severity": "low",
        "summary": "Synthetic HTTP feedback record only.",
    }
    hazard_payload = {
        "severity": "high",
        "summary": "Synthetic HTTP hazard report requiring renewed review.",
    }
    with TestClient(app) as client:
        project_id, candidate_id = _queue_synthetic_candidate(client, owner_headers, monkeypatch)
        asyncio.run(_set_user_review_fixture(project_id))
        readiness_url = f"/v1/projects/{project_id}/candidates/{candidate_id}/export-readiness"
        feedback_url = f"/v1/projects/{project_id}/candidates/{candidate_id}/feedback"
        hazard_url = f"/v1/projects/{project_id}/candidates/{candidate_id}:report-hazard"
        approval_id, bundle_id = asyncio.run(
            _seed_synthetic_export_metadata(
                project_id,
                candidate_id,
                approval_status="active",
                bundle_status="ready",
            )
        )
        before_hazard = client.get(f"/v1/projects/{project_id}", headers=owner_headers)
        assert before_hazard.status_code == 200, before_hazard.text
        assert before_hazard.json()["status"] == "user_review"

        assert client.get(readiness_url, headers=other_headers).status_code == 404
        assert (
            client.post(feedback_url, headers=other_headers, json=feedback_payload).status_code
            == 404
        )
        assert (
            client.post(hazard_url, headers=other_headers, json=hazard_payload).status_code == 404
        )

        feedback_response = client.post(feedback_url, headers=owner_headers, json=feedback_payload)
        assert feedback_response.status_code == 201, feedback_response.text
        feedback = feedback_response.json()
        assert feedback["candidate_id"] == candidate_id
        assert feedback["category"] == "fit"

        hazard_response = client.post(hazard_url, headers=owner_headers, json=hazard_payload)
        assert hazard_response.status_code == 201, hazard_response.text
        hazard = hazard_response.json()
        assert hazard["candidate_id"] == candidate_id
        assert hazard["feedback_report_id"]
        assert hazard["status"] == "reported"

        project_response = client.get(f"/v1/projects/{project_id}", headers=owner_headers)
        assert project_response.status_code == 200, project_response.text
        assert project_response.json()["status"] == "risk_review"
        assert project_response.json()["active_risk_assessment_id"] is None
        assert asyncio.run(_authorization_statuses(approval_id, bundle_id)) == (
            "invalidated",
            "revoked",
        )

        readiness_response = client.get(readiness_url, headers=owner_headers)
        assert readiness_response.status_code == 200, readiness_response.text
        assert readiness_response.json()["allowed"] is False

        monkeypatch.setattr(
            "accessforge.exports.service.get_private_bytes",
            lambda **_: pytest.fail("A revoked synthetic bundle must not be read from storage."),
        )
        blocked_download = client.get(
            f"/v1/projects/{project_id}/exports/{bundle_id}/download",
            headers=owner_headers,
        )
        assert blocked_download.status_code == 409, blocked_download.text


def test_invalidated_acknowledgement_blocks_a_ready_synthetic_bundle_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_headers = api_headers(f"phase6-invalid-download-{uuid4()}")
    with TestClient(app) as client:
        project_id, candidate_id = _queue_synthetic_candidate(client, owner_headers, monkeypatch)
        _, bundle_id = asyncio.run(
            _seed_synthetic_export_metadata(
                project_id,
                candidate_id,
                approval_status="invalidated",
                bundle_status="ready",
            )
        )
        monkeypatch.setattr(
            "accessforge.exports.service.get_private_bytes",
            lambda **_: pytest.fail(
                "An invalidated acknowledgement must not be read from storage."
            ),
        )
        response = client.get(
            f"/v1/projects/{project_id}/exports/{bundle_id}/download",
            headers=owner_headers,
        )
        assert response.status_code == 409, response.text
        assert "acknowledgement is no longer current" in response.json()["detail"]


def test_ready_metadata_download_reruns_current_default_denied_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_headers = api_headers(f"phase6-current-readiness-download-{uuid4()}")
    with TestClient(app) as client:
        project_id, candidate_id = _queue_synthetic_candidate(client, owner_headers, monkeypatch)
        _, bundle_id = asyncio.run(
            _seed_synthetic_export_metadata(
                project_id,
                candidate_id,
                approval_status="active",
                bundle_status="ready",
            )
        )
        monkeypatch.setattr(
            "accessforge.exports.service.get_private_bytes",
            lambda **_: pytest.fail("Current default-denied readiness must be checked first."),
        )
        response = client.get(
            f"/v1/projects/{project_id}/exports/{bundle_id}/download",
            headers=owner_headers,
        )
        assert response.status_code == 409, response.text


def test_authenticated_bundle_delivery_uses_a_no_store_zip_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise only the authenticated transport shape, never a real export gate."""

    owner_headers = api_headers(f"phase6-authenticated-delivery-{uuid4()}")

    async def synthetic_authorized_delivery(*_: object, **__: object) -> tuple[object, bytes]:
        return object(), b"SYNTHETIC ZIP RESPONSE ONLY"

    monkeypatch.setattr(
        "accessforge.api.routes.exports.load_private_export_bundle_for_download",
        synthetic_authorized_delivery,
    )
    with TestClient(app) as client:
        project_id, _ = _queue_synthetic_candidate(client, owner_headers, monkeypatch)
        response = client.get(
            f"/v1/projects/{project_id}/exports/synthetic-bundle/download",
            headers=owner_headers,
        )

    assert response.status_code == 200, response.text
    assert response.content == b"SYNTHETIC ZIP RESPONSE ONLY"
    assert response.headers["content-type"].startswith("application/zip")
    assert response.headers["cache-control"] == "no-store, private"
    assert "attachment" in response.headers["content-disposition"]


def test_openapi_declares_the_phase6_controlled_export_and_feedback_contracts() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    candidate_prefix = "/v1/projects/{project_id}/candidates/{candidate_id}"
    assert {
        f"{candidate_prefix}/export-readiness",
        f"{candidate_prefix}:approve-export",
        f"{candidate_prefix}:export",
        f"{candidate_prefix}/exports",
        f"{candidate_prefix}/feedback",
        f"{candidate_prefix}:report-hazard",
        f"{candidate_prefix}/controlled-validation",
        "/v1/projects/{project_id}/exports/{bundle_id}/download",
        "/v1/controlled-validation/template-release-controls",
    } <= set(paths)
    approval_operation = paths[f"{candidate_prefix}:approve-export"]["post"]
    assert approval_operation["responses"]["201"]
    assert any(
        parameter["name"] == "Idempotency-Key" and parameter["required"] is True
        for parameter in approval_operation["parameters"]
    )
    download_response = paths["/v1/projects/{project_id}/exports/{bundle_id}/download"]["get"][
        "responses"
    ]["200"]
    assert "application/zip" in download_response["content"]
    assert "application/json" not in download_response["content"]
    assert paths[f"{candidate_prefix}/feedback"]["post"]["responses"]["201"]
    assert paths[f"{candidate_prefix}:report-hazard"]["post"]["responses"]["201"]
