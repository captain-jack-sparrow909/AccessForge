"""Pure Phase 6 contract tests using synthetic, non-human inputs only."""

from __future__ import annotations

import base64
import hashlib
import io
import zipfile

import pytest
from pydantic import ValidationError

from accessforge.exports.bundle import (
    BundleArtifact,
    ExportBundleError,
    build_export_bundle,
    verify_export_bundle,
)
from accessforge.exports.protocol import (
    CONTROLLED_VALIDATION_PROTOCOL_VERSION,
    ControlledPhysicalValidationInput,
    recorded_result,
)
from accessforge.risk.private_context import (
    RiskContextSealError,
    context_hash,
    open_risk_context,
    seal_risk_context,
)
from accessforge.risk.schemas import RiskContextInput


def synthetic_risk_context() -> RiskContextInput:
    return RiskContextInput(
        intended_use="SYNTHETIC TEST ONLY: a passive software-model pull-tab example.",
        body_contact="none",
        load="none",
        temperature="room_temperature",
        chemicals="none",
        electricity="none",
        age_group="adult",
        safety_feature_interaction="none",
        failure_consequence="minor_inconvenience",
        duration="occasional",
        fatigue="not_expected",
        manufacturing_uncertainty="bounded",
    )


def synthetic_bundle_artifacts() -> list[BundleArtifact]:
    layout = {
        "design_step": "design.step",
        "design_stl": "design.stl",
        "preview_glb": "preview.glb",
        "design_spec_json": "design-spec.json",
        "validation_report_json": "validation-report.json",
        "readme_txt": "README.txt",
        "provenance_json": "provenance.json",
    }
    artifacts: list[BundleArtifact] = []
    for kind, filename in layout.items():
        content = f"SYNTHETIC TEST ARTIFACT: {kind}\n".encode()
        artifacts.append(
            BundleArtifact(
                kind=kind,
                filename=filename,
                checksum_sha256=hashlib.sha256(content).hexdigest(),
                size_bytes=len(content),
                content=content,
            )
        )
    return artifacts


def build_synthetic_bundle() -> bytes:
    return build_export_bundle(
        artifacts=synthetic_bundle_artifacts(),
        report_text=(
            "Synthetic test record only. This bundle does not authorize manufacture "
            "or physical use."
        ),
        print_guidance={
            "process": "Synthetic fixture-record guidance only.",
            "limitations": "No printability, material, safety, fit, or performance conclusion.",
        },
        lineage={
            "candidate_id": "synthetic-candidate-1",
            "design_spec_hash": "a" * 64,
            "risk_assessment_id": "synthetic-risk-1",
        },
    ).content


def rewrite_zip_entry(bundle: bytes, path: str, replacement: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(bundle), "r") as source:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as destination:
            for name in source.namelist():
                destination.writestr(name, replacement if name == path else source.read(name))
    return output.getvalue()


def test_export_bundle_is_deterministic_and_verifies_all_synthetic_entries() -> None:
    first = build_synthetic_bundle()
    second = build_synthetic_bundle()

    assert first == second
    verified, errors = verify_export_bundle(first)
    assert verified is True
    assert errors == []

    with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
        assert set(archive.namelist()) == {
            "EXPORT-REPORT.txt",
            "PRINT-GUIDANCE.txt",
            "artifacts/README.txt",
            "artifacts/design-spec.json",
            "artifacts/design.step",
            "artifacts/design.stl",
            "artifacts/preview.glb",
            "artifacts/provenance.json",
            "artifacts/validation-report.json",
            "export-manifest.json",
        }
        report = archive.read("EXPORT-REPORT.txt")
        assert b"does not authorize manufacture or physical use" in report


def test_export_bundle_verification_fails_when_an_artifact_byte_is_tampered() -> None:
    tampered = rewrite_zip_entry(
        build_synthetic_bundle(),
        "artifacts/design.stl",
        b"SYNTHETIC TEST ARTIFACT: tampered byte\n",
    )

    verified, errors = verify_export_bundle(tampered)

    assert verified is False
    assert any("hash does not verify" in error for error in errors)


def test_export_bundle_builder_rejects_synthetic_artifact_metadata_mismatch() -> None:
    artifacts = synthetic_bundle_artifacts()
    altered = artifacts[0]
    artifacts[0] = BundleArtifact(
        kind=altered.kind,
        filename=altered.filename,
        checksum_sha256="0" * 64,
        size_bytes=altered.size_bytes,
        content=altered.content,
    )

    with pytest.raises(ExportBundleError, match="hash does not match immutable metadata"):
        build_export_bundle(
            artifacts=artifacts,
            report_text="Synthetic test record only.",
            print_guidance={"limitations": "Synthetic only; no physical-use conclusion."},
            lineage={"candidate_id": "synthetic-candidate-1"},
        )


def synthetic_protocol_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": CONTROLLED_VALIDATION_PROTOCOL_VERSION,
        "record_type": "dimensional_fixture",
        "process_record": {
            "process": "fdm",
            "material_profile": "pla_provisional",
            "printer_reference": "synthetic-printer-fixture",
            "material_batch_reference": "synthetic-material-batch",
            "orientation_record": "synthetic orientation observation",
            "nozzle_diameter_mm": 0.4,
            "layer_height_mm": 0.2,
            "calibration_reference": "synthetic-calibration-reference",
        },
        "measured_dimensions": [
            {
                "label": "synthetic fixture width",
                "nominal_mm": 10.0,
                "observed_mm": 10.1,
                "tolerance_mm": 0.2,
            }
        ],
        "stop_criteria_observed": [],
        "evidence_hashes": ["b" * 64],
    }
    payload.update(overrides)
    return payload


def test_controlled_protocol_derives_observation_status_without_a_pass_claim() -> None:
    within = ControlledPhysicalValidationInput.model_validate(synthetic_protocol_payload())
    outside = ControlledPhysicalValidationInput.model_validate(
        synthetic_protocol_payload(
            measured_dimensions=[
                {
                    "label": "synthetic fixture width",
                    "nominal_mm": 10.0,
                    "observed_mm": 10.3,
                    "tolerance_mm": 0.2,
                }
            ]
        )
    )
    stopped = ControlledPhysicalValidationInput.model_validate(
        synthetic_protocol_payload(stop_criteria_observed=["crack"])
    )

    assert recorded_result(within) == "within_recorded_tolerance"
    assert recorded_result(outside) == "outside_recorded_tolerance"
    assert recorded_result(stopped) == "stopped_for_recorded_criterion"


@pytest.mark.parametrize(
    "overrides",
    [
        {"stop_criteria_observed": ["unapproved_stop_criterion"]},
        {"evidence_hashes": ["upper".ljust(64, "A")]},
        {"unexpected": "extra fields are prohibited"},
    ],
)
def test_controlled_protocol_rejects_unverifiable_or_undeclared_synthetic_input(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ControlledPhysicalValidationInput.model_validate(synthetic_protocol_payload(**overrides))


def encoded_risk_context_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def test_sealed_risk_context_round_trips_and_hashes_without_exposing_plaintext() -> None:
    context = synthetic_risk_context()
    raw_marker = "SYNTHETIC TEST ONLY"
    sealed = seal_risk_context(
        context,
        key=encoded_risk_context_key(),
        project_id="synthetic-project-1",
        assessment_id="synthetic-assessment-1",
    )

    assert sealed.startswith("afrc1.")
    assert raw_marker not in sealed
    assert len(context_hash(context)) == 64
    assert (
        open_risk_context(
            sealed,
            key=encoded_risk_context_key(),
            project_id="synthetic-project-1",
            assessment_id="synthetic-assessment-1",
        )
        == context
    )


@pytest.mark.parametrize(
    ("project_id", "assessment_id"),
    [
        ("different-synthetic-project", "synthetic-assessment-1"),
        ("synthetic-project-1", "different-synthetic-assessment"),
    ],
)
def test_sealed_risk_context_rejects_wrong_lineage(project_id: str, assessment_id: str) -> None:
    sealed = seal_risk_context(
        synthetic_risk_context(),
        key=encoded_risk_context_key(),
        project_id="synthetic-project-1",
        assessment_id="synthetic-assessment-1",
    )

    with pytest.raises(RiskContextSealError, match="unavailable for revalidation"):
        open_risk_context(
            sealed,
            key=encoded_risk_context_key(),
            project_id=project_id,
            assessment_id=assessment_id,
        )


def test_sealed_risk_context_rejects_tampered_ciphertext_and_wrong_key() -> None:
    key = encoded_risk_context_key()
    sealed = seal_risk_context(
        synthetic_risk_context(),
        key=key,
        project_id="synthetic-project-1",
        assessment_id="synthetic-assessment-1",
    )
    tampered = f"{sealed[:-1]}{'A' if sealed[-1] != 'A' else 'B'}"
    wrong_key = base64.urlsafe_b64encode(bytes(range(1, 33))).decode("ascii").rstrip("=")

    with pytest.raises(RiskContextSealError, match="unavailable for revalidation"):
        open_risk_context(
            tampered,
            key=key,
            project_id="synthetic-project-1",
            assessment_id="synthetic-assessment-1",
        )
    with pytest.raises(RiskContextSealError, match="unavailable for revalidation"):
        open_risk_context(
            sealed,
            key=wrong_key,
            project_id="synthetic-project-1",
            assessment_id="synthetic-assessment-1",
        )
