"""Golden geometry and trust-boundary checks for the Phase 4 CAD foundation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from accessforge.cad.compiler import compile_design_spec, write_compilation_result
from accessforge.cad.registry import (
    TemplateRegistryError,
    get_template_release,
    list_template_releases,
    validate_design_spec,
)
from accessforge.cad.sandbox import CadIsolationError, _read_result, run_isolated_compilation
from accessforge.cad.schemas import (
    DesignSpec,
    FieldProvenance,
    ManufacturingProfile,
    canonical_length_from_entry,
)


def fixture_payload(template_id: str) -> dict[str, object]:
    release = get_template_release(template_id, "1.0.0")
    fixture_path = release.release_path / "preview-fixture.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def fixture_spec(template_id: str) -> DesignSpec:
    release = get_template_release(template_id, "1.0.0")
    fixture = fixture_payload(template_id)
    fixture_parameters = fixture["parameters"]
    assert isinstance(fixture_parameters, dict)
    parameters = {
        name: canonical_length_from_entry(value, "mm") for name, value in fixture_parameters.items()
    }
    provenance_paths = {
        "schema_version",
        "project_id",
        "requirements_revision_id",
        "template_id",
        "template_version",
        "template_manifest_sha256",
        "manufacturing",
        "manufacturing.nozzle_diameter",
        "manufacturing.layer_height",
        "fit_clearance",
        "dimensional_tolerance",
        "uses_assessed",
        "uses_not_assessed",
        "risk_tier",
        "risk_rule_set_version",
        "confirmed_assumptions",
        "unresolved_assumptions",
        "generation_seed",
        *(f"parameters.{name}" for name in parameters),
    }
    provenance = {
        path: FieldProvenance(
            creator_type="reviewer",
            source_ref=f"fixture:{template_id}:1.0.0",
            rationale="Synthetic deterministic CAD fixture.",
        )
        for path in provenance_paths
    }
    return DesignSpec(
        project_id="00000000-0000-0000-0000-000000000001",
        requirements_revision_id="00000000-0000-0000-0000-000000000002",
        template_id=template_id,
        template_version="1.0.0",
        template_manifest_sha256=release.manifest_sha256,
        parameters=parameters,
        manufacturing=ManufacturingProfile(
            process="fdm",
            material_profile="pla_provisional",
            nozzle_diameter=canonical_length_from_entry(0.4, "mm"),
            layer_height=canonical_length_from_entry(0.2, "mm"),
        ),
        fit_clearance=canonical_length_from_entry(0.4, "mm"),
        dimensional_tolerance=canonical_length_from_entry(0.15, "mm"),
        uses_assessed=("Synthetic deterministic CAD fixture only.",),
        uses_not_assessed=("Strength, safety, fit, and physical use are not assessed.",),
        risk_tier="R1",
        risk_rule_set_version="fixture-risk-rules.v1",
        confirmed_assumptions=("This is a synthetic test fixture.",),
        unresolved_assumptions=(),
        generation_seed=str(fixture["generation_seed"]),
        field_provenance=provenance,
    )


def spec_with_parameters(spec: DesignSpec, **values_mm: float) -> DesignSpec:
    payload = spec.model_dump(mode="json")
    parameters = payload["parameters"]
    assert isinstance(parameters, dict)
    for name, value in values_mm.items():
        parameter = parameters[name]
        assert isinstance(parameter, dict)
        parameter["canonical_value_m"] = value / 1000
        parameter["original_value"] = value
        parameter["original_unit"] = "mm"
    return DesignSpec.model_validate(payload)


def test_registry_exposes_only_the_three_static_reviewed_releases() -> None:
    releases = list_template_releases()
    assert [(release.manifest.template_id, release.manifest.version) for release in releases] == [
        ("cylindrical_grip_thickener", "1.0.0"),
        ("handle_sleeve", "1.0.0"),
        ("pull_tab_extender", "1.0.0"),
    ]
    with pytest.raises(TemplateRegistryError, match="not reviewed"):
        get_template_release("untrusted_template", "1.0.0")


@pytest.mark.parametrize(
    "template_id",
    ["pull_tab_extender", "cylindrical_grip_thickener", "handle_sleeve"],
)
def test_fixture_spec_compiles_to_a_complete_deterministic_bundle(
    template_id: str, tmp_path: Path
) -> None:
    spec = fixture_spec(template_id)
    first = compile_design_spec(spec, tmp_path / "first")
    second = compile_design_spec(spec, tmp_path / "second")
    assert set(first.artifacts) == {
        "design_step",
        "design_stl",
        "preview_glb",
        "design_spec_json",
        "validation_report_json",
        "readme_txt",
        "provenance_json",
    }
    assert first.geometry_summary["geometry_hash"] == second.geometry_summary["geometry_hash"]
    assert first.artifact_metadata == second.artifact_metadata
    fixture = fixture_payload(template_id)
    expected_dimensions = fixture["expected_dimensions_mm"]
    assert isinstance(expected_dimensions, dict)
    actual_dimensions = first.geometry_summary["bounding_box_mm"]
    assert isinstance(actual_dimensions, dict)
    for axis, expected in expected_dimensions.items():
        assert actual_dimensions[axis] == pytest.approx(expected, abs=0.15)
    findings = first.validation_report["findings"]
    assert isinstance(findings, list)
    failed = [
        finding
        for finding in findings
        if isinstance(finding, dict) and finding["status"] == "failed"
    ]
    assert failed == []


def test_out_of_range_parameter_fails_before_compilation() -> None:
    spec = fixture_spec("pull_tab_extender")
    payload = spec.model_dump(mode="json")
    payload["parameters"]["body_thickness"]["canonical_value_m"] = 0.01
    payload["parameters"]["body_thickness"]["original_value"] = 10.0
    invalid = DesignSpec.model_validate(payload)
    with pytest.raises(TemplateRegistryError, match="never silently clamps"):
        validate_design_spec(invalid)


@pytest.mark.parametrize(
    "template_id",
    ["pull_tab_extender", "cylindrical_grip_thickener", "handle_sleeve"],
)
def test_each_declared_parameter_boundary_validates_before_compilation(template_id: str) -> None:
    spec = fixture_spec(template_id)
    release = get_template_release(template_id, "1.0.0")
    for name, parameter in release.manifest.parameters.items():
        for value in (parameter.minimum, parameter.maximum):
            companion_values: dict[str, float] = {}
            if (
                template_id == "handle_sleeve"
                and name == "handle_diameter"
                and value == parameter.maximum
            ):
                companion_values["outer_diameter"] = 55.0
            if (
                template_id == "handle_sleeve"
                and name == "outer_diameter"
                and value == parameter.minimum
            ):
                companion_values.update({"handle_diameter": 6.0, "fit_clearance": 0.3})
            bounded = spec_with_parameters(spec, **companion_values, **{name: value})
            assert validate_design_spec(bounded).key == release.key


@pytest.mark.parametrize(
    "template_id",
    ["pull_tab_extender", "cylindrical_grip_thickener", "handle_sleeve"],
)
def test_each_outside_range_parameter_is_rejected_before_compilation(template_id: str) -> None:
    spec = fixture_spec(template_id)
    release = get_template_release(template_id, "1.0.0")
    for name, parameter in release.manifest.parameters.items():
        for value in (parameter.minimum - 0.001, parameter.maximum + 0.001):
            with pytest.raises(TemplateRegistryError, match=f"{name} must be between"):
                validate_design_spec(spec_with_parameters(spec, **{name: value}))


def test_missing_parameter_is_rejected_before_the_compiler_can_run() -> None:
    payload = fixture_spec("pull_tab_extender").model_dump(mode="json")
    parameters = payload["parameters"]
    assert isinstance(parameters, dict)
    parameters.pop("body_thickness")
    with pytest.raises(ValueError, match="unexpected provenance"):
        DesignSpec.model_validate(payload)


@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_dimensions_are_rejected_before_the_compiler_can_run(
    invalid_value: float,
) -> None:
    payload = fixture_spec("pull_tab_extender").model_dump(mode="python")
    parameters = payload["parameters"]
    assert isinstance(parameters, dict)
    body_thickness = parameters["body_thickness"]
    assert isinstance(body_thickness, dict)
    body_thickness["canonical_value_m"] = invalid_value
    body_thickness["original_value"] = invalid_value
    with pytest.raises(ValueError):
        DesignSpec.model_validate(payload)


@pytest.mark.parametrize(
    ("template_id", "updates", "message"),
    [
        (
            "pull_tab_extender",
            {"attachment_slot_width": 24.0, "pull_loop_outer_width": 20.0},
            "insufficient material",
        ),
        (
            "cylindrical_grip_thickener",
            {"inner_diameter": 22.0, "outer_diameter": 16.0},
            "outer diameter must exceed",
        ),
        (
            "handle_sleeve",
            {"handle_diameter": 35.0, "fit_clearance": 2.0, "outer_diameter": 18.0},
            "outer diameter must exceed",
        ),
    ],
)
def test_cross_parameter_geometry_constraints_fail_before_compilation(
    template_id: str, updates: dict[str, float], message: str
) -> None:
    invalid_geometry = spec_with_parameters(fixture_spec(template_id), **updates)
    with pytest.raises(TemplateRegistryError, match=message):
        validate_design_spec(invalid_geometry)


def test_isolated_compiler_returns_fixed_artifacts_without_template_code() -> None:
    result = run_isolated_compilation(fixture_spec("pull_tab_extender"))
    assert result.artifact_metadata["preview_glb"]["content_type"] == "model/gltf-binary"
    assert result.provenance["template"]["template_id"] == "pull_tab_extender"


def test_parent_rejects_tampered_child_artifact_metadata(tmp_path: Path) -> None:
    output_directory = tmp_path / "compiler-output"
    result = compile_design_spec(fixture_spec("pull_tab_extender"), output_directory)
    write_compilation_result(result, output_directory)
    manifest_path = output_directory / "result.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_metadata"]["design_step"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CadIsolationError, match="does not match"):
        _read_result(output_directory)
