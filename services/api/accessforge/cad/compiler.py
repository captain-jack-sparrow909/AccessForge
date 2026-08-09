"""Deterministic compilation and intentionally limited Phase 4 geometry checks."""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import trimesh

from accessforge.cad.registry import (
    TemplateRegistryError,
    parameter_values_mm,
    validate_design_spec,
)
from accessforge.cad.schemas import DesignSpec, canonical_hash, canonical_json
from accessforge.cad.templates import build_template

ValidationStatus = Literal["passed", "failed", "needs_confirmation", "not_assessed", "error"]
Severity = Literal["info", "warning", "error"]
ValidationValue = float | int | str | bool | None | list[float]


class CadCompilationError(RuntimeError):
    """The trusted compiler could not produce a complete candidate bundle."""


@dataclass(frozen=True)
class ValidationFinding:
    check_id: str
    check_version: str
    status: ValidationStatus
    severity: Severity
    measured_value: ValidationValue
    threshold: ValidationValue
    unit: str | None
    evidence: dict[str, object]
    plain_language_explanation: str
    remediation: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "check_version": self.check_version,
            "status": self.status,
            "severity": self.severity,
            "measured_value": self.measured_value,
            "threshold": self.threshold,
            "unit": self.unit,
            "evidence": self.evidence,
            "plain_language_explanation": self.plain_language_explanation,
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class CompilationResult:
    artifacts: dict[str, bytes]
    artifact_metadata: dict[str, dict[str, object]]
    geometry_summary: dict[str, object]
    validation_report: dict[str, object]
    provenance: dict[str, object]


_ARTIFACT_FILENAMES: dict[str, str] = {
    "design_step": "design.step",
    "design_stl": "design.stl",
    "preview_glb": "preview.glb",
    "design_spec_json": "design-spec.json",
    "validation_report_json": "validation-report.json",
    "readme_txt": "README.txt",
    "provenance_json": "provenance.json",
}

_ARTIFACT_CONTENT_TYPES: dict[str, str] = {
    "design_step": "application/step",
    "design_stl": "model/stl",
    "preview_glb": "model/gltf-binary",
    "design_spec_json": "application/json",
    "validation_report_json": "application/json",
    "readme_txt": "text/plain; charset=utf-8",
    "provenance_json": "application/json",
}

_STEP_FILE_NAME_TIMESTAMP = re.compile(r"(FILE_NAME\('[^']*',')[^']*(')")
_STEP_TRANSLATOR_SEQUENCE = re.compile(r"(Open CASCADE STEP translator [0-9.]+) [0-9]+")


def _normalize_step_export(path: Path) -> None:
    """Remove exporter-only STEP header variance without changing geometry.

    OpenCascade writes its current wall-clock time and a per-export translator
    sequence into otherwise equivalent STEP output.  Both are informational
    strings, not B-Rep entities.  Normalising them makes bundle hashes useful
    within the recorded compiler environment while retaining a valid STEP file.
    """

    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CadCompilationError("The trusted STEP export was not UTF-8 text.") from exc
    normalized = _STEP_FILE_NAME_TIMESTAMP.sub(r"\g<1>1970-01-01T00:00:00\g<2>", source)
    normalized = _STEP_TRANSLATOR_SEQUENCE.sub(r"\g<1> deterministic", normalized)
    path.write_text(normalized, encoding="utf-8")


def compiler_fingerprint() -> dict[str, str]:
    """Version data that makes a geometry result auditable, not portable by claim."""

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cadquery": importlib.metadata.version("cadquery"),
        "cadquery_ocp": importlib.metadata.version("cadquery-ocp"),
        "trimesh": importlib.metadata.version("trimesh"),
        "cad_units": "mm (converted from canonical DesignSpec metres at compiler boundary)",
        "step_export_normalization": "header-v1",
    }


def _artifact_metadata(artifacts: Mapping[str, bytes]) -> dict[str, dict[str, object]]:
    return {
        kind: {
            "filename": _ARTIFACT_FILENAMES[kind],
            "content_type": _ARTIFACT_CONTENT_TYPES[kind],
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for kind, content in artifacts.items()
    }


def _findings_for_mesh(
    *,
    mesh: trimesh.Trimesh,
    expected_dimensions_mm: Mapping[str, float],
    tolerance_mm: float,
) -> tuple[list[ValidationFinding], dict[str, object]]:
    bounds = mesh.bounds
    extents = [round(float(value), 6) for value in mesh.extents]
    components = list(mesh.split(only_watertight=False))
    geometry = {
        "bounding_box_mm": {"x": extents[0], "y": extents[1], "z": extents[2]},
        "bounds_mm": {
            "minimum": [round(float(value), 6) for value in bounds[0]],
            "maximum": [round(float(value), 6) for value in bounds[1]],
        },
        "face_count": int(len(mesh.faces)),
        "vertex_count": int(len(mesh.vertices)),
        "component_count": len(components),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "volume_mm3": round(float(mesh.volume), 6) if mesh.is_volume else None,
    }
    expected_vector = [
        round(float(expected_dimensions_mm.get(axis, extents[index])), 6)
        for index, axis in enumerate(("x", "y", "z"))
    ]
    dimension_errors = [
        abs(actual - expected) for actual, expected in zip(extents, expected_vector, strict=True)
    ]
    dimensions_ok = all(error <= tolerance_mm for error in dimension_errors)
    findings = [
        ValidationFinding(
            check_id="design-spec-schema",
            check_version="phase4.v1",
            status="passed",
            severity="info",
            measured_value="valid",
            threshold="valid",
            unit=None,
            evidence={},
            plain_language_explanation=(
                "The immutable DesignSpec and reviewed template range checks passed."
            ),
            remediation=None,
        ),
        ValidationFinding(
            check_id="expected-bounding-dimensions",
            check_version="phase4.v1",
            status="passed" if dimensions_ok else "failed",
            severity="info" if dimensions_ok else "error",
            measured_value=extents,
            threshold=expected_vector,
            unit="mm",
            evidence={"absolute_error_mm": dimension_errors},
            plain_language_explanation=(
                "Generated mesh dimensions match this template's deterministic expectation."
                if dimensions_ok
                else (
                    "Generated mesh dimensions differ from this template's "
                    "deterministic expectation."
                )
            ),
            remediation=None
            if dimensions_ok
            else "Do not use this candidate; inspect the compiler release.",
        ),
        ValidationFinding(
            check_id="mesh-watertightness",
            check_version="phase4.v1",
            status="passed" if mesh.is_watertight else "failed",
            severity="info" if mesh.is_watertight else "error",
            measured_value=bool(mesh.is_watertight),
            threshold=True,
            unit=None,
            evidence={"face_count": len(mesh.faces), "vertex_count": len(mesh.vertices)},
            plain_language_explanation=(
                "The generated STL mesh is watertight."
                if mesh.is_watertight
                else "The generated STL mesh is not watertight."
            ),
            remediation=None
            if mesh.is_watertight
            else "Do not use this candidate; inspect the template.",
        ),
        ValidationFinding(
            check_id="connected-components",
            check_version="phase4.v1",
            status="passed" if len(components) == 1 else "failed",
            severity="info" if len(components) == 1 else "error",
            measured_value=len(components),
            threshold=1,
            unit="components",
            evidence={},
            plain_language_explanation=(
                "The generated mesh has one connected component."
                if len(components) == 1
                else "The generated mesh has an unexpected number of connected components."
            ),
            remediation=None
            if len(components) == 1
            else "Do not use this candidate; inspect the template.",
        ),
        ValidationFinding(
            check_id="mesh-normal-orientation",
            check_version="phase4.v1",
            status="passed" if mesh.is_winding_consistent else "failed",
            severity="info" if mesh.is_winding_consistent else "error",
            measured_value=bool(mesh.is_winding_consistent),
            threshold=True,
            unit=None,
            evidence={},
            plain_language_explanation=(
                "The generated mesh has consistent face winding."
                if mesh.is_winding_consistent
                else "The generated mesh has inconsistent face winding."
            ),
            remediation=None
            if mesh.is_winding_consistent
            else "Do not use this candidate; inspect the template.",
        ),
        ValidationFinding(
            check_id="minimum-wall-thickness",
            check_version="phase4.v1",
            status="not_assessed",
            severity="warning",
            measured_value=None,
            threshold=None,
            unit="mm",
            evidence={},
            plain_language_explanation=(
                "Minimum wall thickness has not been assessed by this Phase 4 compiler report."
            ),
            remediation=(
                "Phase 5 validation and physical testing are required before any approval claim."
            ),
        ),
        ValidationFinding(
            check_id="print-orientation-overhang",
            check_version="phase4.v1",
            status="not_assessed",
            severity="warning",
            measured_value=None,
            threshold=None,
            unit=None,
            evidence={},
            plain_language_explanation=(
                "Print orientation and unsupported-overhang behavior have not been assessed."
            ),
            remediation=(
                "Use the template guidance only as a starting point; do not infer printability."
            ),
        ),
    ]
    return findings, geometry


def _expected_dimensions(
    release_parameters: Mapping[str, object], parameters_mm: Mapping[str, float]
) -> dict[str, float]:
    expected: dict[str, float] = {}
    for axis, source in release_parameters.items():
        if isinstance(source, dict):
            parameter = source.get("source_parameter")
            subtract_parameter = source.get("subtract_parameter")
            multiplier = source.get("multiplier", 1)
            offset = source.get("offset_mm", 0)
            if (
                isinstance(parameter, str)
                and isinstance(multiplier, (int, float))
                and isinstance(offset, (int, float))
                and parameter in parameters_mm
            ):
                subtract = 0.0
                if subtract_parameter is not None:
                    if (
                        not isinstance(subtract_parameter, str)
                        or subtract_parameter not in parameters_mm
                    ):
                        continue
                    subtract = parameters_mm[subtract_parameter]
                expected[axis] = round(
                    parameters_mm[parameter] * float(multiplier) + float(offset) - subtract,
                    6,
                )
    return expected


def _plain_language_readme(
    spec: DesignSpec, print_guidance: Mapping[str, str], limitations: tuple[str, ...]
) -> bytes:
    lines = [
        "AccessForge candidate artifact bundle",
        "",
        f"Template: {spec.template_id}@{spec.template_version}",
        f"DesignSpec hash: {spec.content_hash}",
        "",
        (
            "This bundle is a deterministic geometry result, not a safety "
            "certification, fit guarantee,"
        ),
        "medical recommendation, or instruction to manufacture or use a physical part.",
        "Automated validation in this Phase 4 bundle is intentionally limited and lists its gaps.",
        "",
        "Template print guidance (not verified for this candidate):",
    ]
    lines.extend(f"- {item}" for item in print_guidance.values())
    lines.extend(["", "Known limitations:"])
    lines.extend(f"- {item}" for item in limitations)
    return ("\n".join(lines) + "\n").encode("utf-8")


def compile_design_spec(spec: DesignSpec, output_directory: Path) -> CompilationResult:
    """Compile one reviewed spec into a complete, local immutable artifact bundle.

    This function has no networking, database, queue, or object-storage calls.
    The caller is responsible for process isolation and private storage.
    """

    try:
        release = validate_design_spec(spec)
        if spec.risk_tier != "R1" or spec.unresolved_assumptions:
            raise CadCompilationError(
                "The compiler accepts only R1 fixture/spec inputs with no unresolved assumptions."
            )
        parameters_mm = parameter_values_mm(spec)
        shape = build_template(spec.template_id, parameters_mm)
        output_directory.mkdir(parents=True, exist_ok=True)
        step_path = output_directory / _ARTIFACT_FILENAMES["design_step"]
        stl_path = output_directory / _ARTIFACT_FILENAMES["design_stl"]
        # Lazy import shares the explicitly initialised VTK/CadQuery runtime from
        # templates._cadquery and avoids loading native CAD libraries in the API process.
        from accessforge.cad.templates import _cadquery

        cq = _cadquery()
        cq.exporters.export(shape, str(step_path), exportType="STEP")
        _normalize_step_export(step_path)
        cq.exporters.export(
            shape, str(stl_path), exportType="STL", tolerance=0.05, angularTolerance=0.1
        )
        mesh = trimesh.load_mesh(stl_path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            raise CadCompilationError("The trusted STL export did not contain a single mesh.")
        glb = mesh.export(file_type="glb")
        if not isinstance(glb, bytes):
            raise CadCompilationError("The trusted preview export did not produce GLB bytes.")
        expected_dimensions = _expected_dimensions(
            release.manifest.expected_dimensions, parameters_mm
        )
        tolerance_mm = 0.15
        policy_tolerance = release.manifest.validation_policy.get("bounding_dimension_tolerance_mm")
        if isinstance(policy_tolerance, (int, float)) and policy_tolerance > 0:
            tolerance_mm = float(policy_tolerance)
        findings, geometry = _findings_for_mesh(
            mesh=mesh,
            expected_dimensions_mm=expected_dimensions,
            tolerance_mm=tolerance_mm,
        )
        validation_report: dict[str, object] = {
            "report_schema_version": "1.0",
            "report_type": "phase4_geometry_checks",
            "limitations": (
                "These checks do not certify fitness, safety, strength, "
                "printability, or accessibility."
            ),
            "findings": [finding.as_dict() for finding in findings],
        }
        artifacts: dict[str, bytes] = {
            "design_step": step_path.read_bytes(),
            "design_stl": stl_path.read_bytes(),
            "preview_glb": glb,
            "design_spec_json": (canonical_json(spec.canonical_payload()) + "\n").encode("utf-8"),
            "validation_report_json": (canonical_json(validation_report) + "\n").encode("utf-8"),
            "readme_txt": _plain_language_readme(
                spec, release.manifest.print_guidance, release.manifest.known_limitations
            ),
        }
        geometry["geometry_hash"] = canonical_hash(geometry)
        core_metadata = _artifact_metadata(artifacts)
        provenance = {
            "provenance_schema_version": "1.0",
            "design_spec_hash": spec.content_hash,
            "template": {
                "template_id": release.manifest.template_id,
                "version": release.manifest.version,
                "manifest_sha256": release.manifest_sha256,
                "release_policy": release.manifest.status,
            },
            "generation_seed": spec.generation_seed,
            "compiler": compiler_fingerprint(),
            "geometry": geometry,
            "validation_report_sha256": core_metadata["validation_report_json"]["sha256"],
            # The provenance file does not include a hash of itself, avoiding a
            # misleading self-referential hash.  Its own hash is recorded by the
            # artifact store alongside every other immutable artifact.
            "artifact_hashes_excluding_provenance": {
                kind: data["sha256"] for kind, data in core_metadata.items()
            },
        }
        artifacts["provenance_json"] = (canonical_json(provenance) + "\n").encode("utf-8")
        metadata = _artifact_metadata(artifacts)
        total_size = sum(len(content) for content in artifacts.values())
        if total_size > 50_000_000:
            raise CadCompilationError("The compiler bundle exceeded the 50 MB output limit.")
        return CompilationResult(
            artifacts=artifacts,
            artifact_metadata=metadata,
            geometry_summary=geometry,
            validation_report=validation_report,
            provenance=provenance,
        )
    except (TemplateRegistryError, OSError, ValueError) as exc:
        raise CadCompilationError(str(exc)) from exc


def write_compilation_result(result: CompilationResult, output_directory: Path) -> None:
    """Write only fixed artifact names to a disposable compiler workspace."""

    output_directory.mkdir(parents=True, exist_ok=True)
    for kind, content in result.artifacts.items():
        filename = _ARTIFACT_FILENAMES.get(kind)
        if filename is None:
            raise CadCompilationError("Compiler attempted to write an undeclared artifact kind.")
        (output_directory / filename).write_bytes(content)
    summary = {
        "artifact_kinds": sorted(result.artifacts),
        "artifact_metadata": result.artifact_metadata,
        "geometry_summary": result.geometry_summary,
        "validation_report": result.validation_report,
        "provenance": result.provenance,
    }
    (output_directory / "result.json").write_text(canonical_json(summary) + "\n", encoding="utf-8")
