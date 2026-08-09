"""HTTP coverage for the immutable Phase 5 deterministic risk and planning gate."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_phase4_design_api import (
    api_headers,
    create_confirmed_project,
    pull_tab_design_spec_payload,
)

from accessforge.main import app


def risk_payload(design_spec_id: str, *, intended_use: str) -> dict[str, str]:
    return {
        "design_spec_id": design_spec_id,
        "intended_use": intended_use,
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


def create_phase5_spec(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    project_id = create_confirmed_project(client, headers)
    response = client.post(
        f"/v1/projects/{project_id}/design-specs",
        headers=headers,
        json=pull_tab_design_spec_payload(seed=f"phase5-risk-{uuid4()}"),
    )
    assert response.status_code == 201, response.text
    return project_id, response.json()["id"]


def test_r1_assessment_clones_a_risk_bound_spec_and_pauses_a_bounded_plan() -> None:
    headers = api_headers(f"phase5-r1-{uuid4()}")
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, headers)
        response = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=headers,
            json=risk_payload(
                source_spec_id,
                intended_use=(
                    "A passive room-temperature pull-tab extension for a jacket zipper during "
                    "a low-energy occasional pull."
                ),
            ),
        )
        assert response.status_code == 201, response.text
        assessment = response.json()
        assert assessment["tier"] == "R1"
        assert assessment["status"] == "current"
        assert "create_design_plan" in assessment["allowed_actions"]
        assert assessment["resulting_design_spec_id"] != source_spec_id
        assert "jacket zipper" not in str(assessment["matched_rules"])

        project = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert project.status_code == 200, project.text
        assert project.json()["status"] == "ready_for_generation"

        plan_response = client.post(
            f"/v1/projects/{project_id}/design-plans",
            headers=headers,
            json={"risk_assessment_id": assessment["id"]},
        )
        assert plan_response.status_code == 201, plan_response.text
        plan = plan_response.json()
        assert plan["status"] == "waiting_for_user"
        assert 2 <= len(plan["proposals"]) <= 3
        assert all(item["design_spec_id"] for item in plan["proposals"])

        chosen = plan["proposals"][0]
        selection = client.post(
            (
                f"/v1/projects/{project_id}/design-plans/{plan['id']}/proposals/"
                f"{chosen['id']}:select"
            ),
            headers=headers,
        )
        assert selection.status_code == 200, selection.text
        selected_plan = selection.json()
        assert selected_plan["status"] == "confirmed"
        assert [item["status"] for item in selected_plan["proposals"]].count("selected") == 1


def test_waiting_plan_queues_an_idempotent_private_comparison_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = api_headers(f"phase5-comparison-{uuid4()}")
    monkeypatch.setattr(
        "accessforge.api.routes.risk.compile_cad_candidate.delay",
        lambda _: None,
    )
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, headers)
        assessment_response = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=headers,
            json=risk_payload(
                source_spec_id,
                intended_use="A passive room-temperature pull-tab extension for a jacket zipper.",
            ),
        )
        assert assessment_response.status_code == 201, assessment_response.text
        plan_response = client.post(
            f"/v1/projects/{project_id}/design-plans",
            headers=headers,
            json={"risk_assessment_id": assessment_response.json()["id"]},
        )
        assert plan_response.status_code == 201, plan_response.text
        plan = plan_response.json()
        idempotency_key = f"phase5-comparison-{uuid4()}"
        queued = client.post(
            f"/v1/projects/{project_id}/design-plans/{plan['id']}:generate-comparison",
            headers={**headers, "Idempotency-Key": idempotency_key},
        )
        assert queued.status_code == 202, queued.text
        batch = queued.json()
        assert batch["status"] == "queued"
        assert 2 <= len(batch["candidates"]) <= 3
        assert all(item["status"] == "queued" for item in batch["candidates"])
        assert all(item["variant_key"] and item["variant_label"] for item in batch["candidates"])
        assert len({item["variant_key"] for item in batch["candidates"]}) == len(
            batch["candidates"]
        )

        duplicate = client.post(
            f"/v1/projects/{project_id}/design-plans/{plan['id']}:generate-comparison",
            headers={**headers, "Idempotency-Key": idempotency_key},
        )
        assert duplicate.status_code == 202, duplicate.text
        assert duplicate.json()["id"] == batch["id"]
        assert [item["id"] for item in duplicate.json()["candidates"]] == [
            item["id"] for item in batch["candidates"]
        ]

        project = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert project.status_code == 200, project.text
        assert project.json()["status"] == "generating"
        plans = client.get(f"/v1/projects/{project_id}/design-plans", headers=headers)
        assert plans.status_code == 200, plans.text
        assert plans.json()[0]["status"] == "comparison_queued"
        assert plans.json()[0]["comparison_batch"]["id"] == batch["id"]
        assert all("validation_limitations" in item for item in batch["candidates"])
        assert all(item["validation_limitations"] == [] for item in batch["candidates"])

        measurement_during_generation = client.post(
            f"/v1/projects/{project_id}/measurements",
            headers=headers,
            json={
                "kind": "late measurement",
                "value": 12,
                "unit": "mm",
                "confirmed": True,
            },
        )
        assert measurement_during_generation.status_code == 409
        observation_during_generation = client.post(
            f"/v1/projects/{project_id}/observations",
            headers=headers,
            json={"text": "A late observation", "input_mode": "text"},
        )
        assert observation_during_generation.status_code == 409


def test_r3_corpus_case_never_opens_generation() -> None:
    headers = api_headers(f"phase5-r3-{uuid4()}")
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, headers)
        response = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=headers,
            json=risk_payload(
                source_spec_id,
                intended_use="An extension for a wheelchair brake control.",
            ),
        )
        assert response.status_code == 201, response.text
        assessment = response.json()
        assert assessment["tier"] == "R3"
        assert "generate_candidate" not in assessment["allowed_actions"]
        assert any(item["tier"] == "R3" for item in assessment["matched_rules"])

        project = client.get(f"/v1/projects/{project_id}", headers=headers)
        assert project.status_code == 200, project.text
        assert project.json()["status"] == "blocked_out_of_scope"

        candidates = client.get(f"/v1/projects/{project_id}/candidates", headers=headers)
        assert candidates.status_code == 200, candidates.text
        assert candidates.json() == []


def test_changed_r3_project_returns_to_review_without_mutating_the_old_decision() -> None:
    headers = api_headers(f"phase5-r3-revise-{uuid4()}")
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, headers)
        blocked = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=headers,
            json=risk_payload(
                source_spec_id,
                intended_use="An extension for a wheelchair brake control.",
            ),
        )
        assert blocked.status_code == 201, blocked.text
        assert blocked.json()["tier"] == "R3"

        correction = client.patch(
            f"/v1/projects/{project_id}",
            headers=headers,
            json={"object_description": "A jacket zipper pull tab."},
        )
        assert correction.status_code == 200, correction.text
        assert correction.json()["status"] == "risk_review"
        assert correction.json()["active_risk_assessment_id"] is None

        rerun = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=headers,
            json=risk_payload(
                source_spec_id,
                intended_use="A passive room-temperature pull-tab extension for a jacket zipper.",
            ),
        )
        assert rerun.status_code == 201, rerun.text
        assert rerun.json()["tier"] == "R1"
        assert rerun.json()["id"] != blocked.json()["id"]


def test_risk_relevant_project_change_invalidates_the_active_r1_decision() -> None:
    headers = api_headers(f"phase5-stale-{uuid4()}")
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, headers)
        assessment = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=headers,
            json=risk_payload(
                source_spec_id,
                intended_use="A passive pull-tab extension for a jacket zipper.",
            ),
        )
        assert assessment.status_code == 201, assessment.text
        update = client.patch(
            f"/v1/projects/{project_id}",
            headers=headers,
            json={"object_description": "A wheelchair brake lever."},
        )
        assert update.status_code == 200, update.text
        assert update.json()["status"] == "risk_review"
        assert update.json()["active_risk_assessment_id"] is None

        current = client.get(f"/v1/projects/{project_id}/risk", headers=headers)
        assert current.status_code == 404
        generation = client.post(
            f"/v1/projects/{project_id}/candidates:generate",
            headers={**headers, "Idempotency-Key": f"phase5-stale-{uuid4()}"},
            json={"design_spec_id": assessment.json()["resulting_design_spec_id"]},
        )
        assert generation.status_code == 409


def test_description_and_observation_changes_invalidate_the_current_r1_decision() -> None:
    description_headers = api_headers(f"phase5-description-stale-{uuid4()}")
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, description_headers)
        assessment = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=description_headers,
            json=risk_payload(
                source_spec_id,
                intended_use="A passive pull-tab extension for a jacket zipper.",
            ),
        )
        assert assessment.status_code == 201, assessment.text
        description_change = client.patch(
            f"/v1/projects/{project_id}",
            headers=description_headers,
            json={"description": "This is actually for a wheelchair brake control."},
        )
        assert description_change.status_code == 200, description_change.text
        assert description_change.json()["status"] == "risk_review"
        assert description_change.json()["active_risk_assessment_id"] is None
        stale_generation = client.post(
            f"/v1/projects/{project_id}/candidates:generate",
            headers={**description_headers, "Idempotency-Key": f"phase5-description-{uuid4()}"},
            json={"design_spec_id": assessment.json()["resulting_design_spec_id"]},
        )
        assert stale_generation.status_code == 409

    observation_headers = api_headers(f"phase5-observation-stale-{uuid4()}")
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, observation_headers)
        assessment = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=observation_headers,
            json=risk_payload(
                source_spec_id,
                intended_use="A passive pull-tab extension for a jacket zipper.",
            ),
        )
        assert assessment.status_code == 201, assessment.text
        observation_change = client.post(
            f"/v1/projects/{project_id}/observations",
            headers=observation_headers,
            json={"text": "This could control a wheelchair brake.", "input_mode": "text"},
        )
        assert observation_change.status_code == 201, observation_change.text
        project = client.get(f"/v1/projects/{project_id}", headers=observation_headers)
        assert project.status_code == 200, project.text
        assert project.json()["status"] == "risk_review"
        assert project.json()["active_risk_assessment_id"] is None
        stale_generation = client.post(
            f"/v1/projects/{project_id}/candidates:generate",
            headers={**observation_headers, "Idempotency-Key": f"phase5-observation-{uuid4()}"},
            json={"design_spec_id": assessment.json()["resulting_design_spec_id"]},
        )
        assert stale_generation.status_code == 409


def test_rejected_plan_variant_cannot_bypass_the_central_generation_gate() -> None:
    headers = api_headers(f"phase5-plan-bypass-{uuid4()}")
    with TestClient(app) as client:
        project_id, source_spec_id = create_phase5_spec(client, headers)
        assessment = client.post(
            f"/v1/projects/{project_id}/risk:assess",
            headers=headers,
            json=risk_payload(
                source_spec_id,
                intended_use="A passive pull-tab extension for a jacket zipper.",
            ),
        )
        assert assessment.status_code == 201, assessment.text
        plan_response = client.post(
            f"/v1/projects/{project_id}/design-plans",
            headers=headers,
            json={"risk_assessment_id": assessment.json()["id"]},
        )
        assert plan_response.status_code == 201, plan_response.text
        plan = plan_response.json()
        selected = plan["proposals"][0]
        rejected = plan["proposals"][1]
        selection = client.post(
            f"/v1/projects/{project_id}/design-plans/{plan['id']}/proposals/{selected['id']}:select",
            headers=headers,
        )
        assert selection.status_code == 200, selection.text
        bypass = client.post(
            f"/v1/projects/{project_id}/candidates:generate",
            headers={**headers, "Idempotency-Key": f"phase5-plan-bypass-{uuid4()}"},
            json={"design_spec_id": rejected["design_spec_id"]},
        )
        assert bypass.status_code == 409
