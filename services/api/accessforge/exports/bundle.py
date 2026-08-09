"""Deterministic assembly and verification of a private Phase 6 ZIP bundle."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass

from accessforge.cad.schemas import canonical_hash, canonical_json

EXPORT_BUNDLE_SCHEMA_VERSION = "1.0"
EXPORT_BUNDLE_FILENAME = "accessforge-controlled-validation-bundle.zip"
_REQUIRED_ARTIFACTS: dict[str, str] = {
    "design_step": "design.step",
    "design_stl": "design.stl",
    "preview_glb": "preview.glb",
    "design_spec_json": "design-spec.json",
    "validation_report_json": "validation-report.json",
    "readme_txt": "README.txt",
    "provenance_json": "provenance.json",
}
_OPTIONAL_ARTIFACTS: dict[str, str] = {"design_3mf": "design.3mf"}
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_MAX_ZIP_ENTRIES = 12
_MAX_ZIP_ENTRY_BYTES = 50_000_000
_MAX_ZIP_TOTAL_BYTES = 100_000_000


class ExportBundleError(ValueError):
    """A private candidate artifact set cannot be safely bundled."""


@dataclass(frozen=True)
class BundleArtifact:
    kind: str
    filename: str
    checksum_sha256: str
    size_bytes: int
    content: bytes


@dataclass(frozen=True)
class ExportBundlePayload:
    content: bytes
    checksum_sha256: str
    manifest: dict[str, object]
    manifest_hash: str


def build_export_bundle(
    *,
    artifacts: list[BundleArtifact],
    report_text: str,
    print_guidance: dict[str, str],
    lineage: dict[str, object],
) -> ExportBundlePayload:
    """Create a fixed-name ZIP after checking every immutable input byte.

    The ZIP contains original compiler artifacts, a plain-language Phase 6
    report, explicit template print guidance, and a hash manifest.  It does not
    label any result safe, fit, printable, approved for manufacture, or ready
    for participant use.
    """

    verified = _verify_artifacts(artifacts)
    report_bytes = _utf8_text(report_text, "The export report")
    guidance_bytes = _guidance_bytes(print_guidance)
    entries: dict[str, bytes] = {
        f"artifacts/{artifact.filename}": artifact.content for artifact in verified
    }
    entries["EXPORT-REPORT.txt"] = report_bytes
    entries["PRINT-GUIDANCE.txt"] = guidance_bytes
    entry_manifest = [
        {
            "path": path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        for path, content in sorted(entries.items())
    ]
    manifest: dict[str, object] = {
        "schema_version": EXPORT_BUNDLE_SCHEMA_VERSION,
        "bundle_kind": "accessforge_controlled_validation_bundle",
        "lineage": lineage,
        "entries_excluding_manifest": entry_manifest,
        "limitations": (
            "This private bundle records exact software artifacts, deterministic checks, and "
            "controlled-validation context. It is not professional approval, a safety "
            "certification, a fit result, a printability guarantee, or permission for "
            "physical use."
        ),
    }
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    entries["export-manifest.json"] = manifest_bytes
    content = _zip_entries(entries)
    return ExportBundlePayload(
        content=content,
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        manifest=manifest,
        manifest_hash=canonical_hash(manifest),
    )


def verify_export_bundle(content: bytes) -> tuple[bool, list[str]]:
    """Verify a downloaded bundle's manifest and fixed ZIP layout."""

    errors: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            names = archive.namelist()
            if len(names) > _MAX_ZIP_ENTRIES:
                return False, ["The export bundle contains too many entries."]
            total_size = sum(info.file_size for info in archive.infolist())
            if total_size > _MAX_ZIP_TOTAL_BYTES or any(
                info.file_size > _MAX_ZIP_ENTRY_BYTES for info in archive.infolist()
            ):
                return False, ["The export bundle exceeds the fixed verification limits."]
            if len(names) != len(set(names)):
                errors.append("The export bundle contains duplicate paths.")
            if any(not _safe_zip_path(name) for name in names):
                errors.append("The export bundle contains an unsafe path.")
            if "export-manifest.json" not in names:
                errors.append("The export bundle is missing its manifest.")
                return False, errors
            try:
                manifest_value = json.loads(archive.read("export-manifest.json"))
            except (json.JSONDecodeError, KeyError, OSError, zipfile.BadZipFile):
                return False, ["The export bundle manifest cannot be read."]
            if not isinstance(manifest_value, dict):
                return False, ["The export bundle manifest is malformed."]
            if (
                manifest_value.get("schema_version") != EXPORT_BUNDLE_SCHEMA_VERSION
                or manifest_value.get("bundle_kind") != "accessforge_controlled_validation_bundle"
            ):
                errors.append("The export bundle manifest has an unsupported schema.")
            entries = manifest_value.get("entries_excluding_manifest")
            if not isinstance(entries, list):
                return False, ["The export bundle manifest does not list its entries."]
            listed_paths: set[str] = set()
            for entry in entries:
                if not isinstance(entry, dict):
                    errors.append("The export bundle manifest has an invalid entry.")
                    continue
                path = entry.get("path")
                checksum = entry.get("sha256")
                size = entry.get("size_bytes")
                if not isinstance(path, str) or not _safe_zip_path(path):
                    errors.append("The export bundle manifest has an unsafe entry path.")
                    continue
                listed_paths.add(path)
                if not isinstance(checksum, str) or len(checksum) != 64:
                    errors.append(f"The export bundle manifest has an invalid hash for {path}.")
                    continue
                if not isinstance(size, int) or size < 0:
                    errors.append(f"The export bundle manifest has an invalid size for {path}.")
                    continue
                if path not in names:
                    errors.append(f"The export bundle is missing {path}.")
                    continue
                entry_bytes = archive.read(path)
                if len(entry_bytes) != size or hashlib.sha256(entry_bytes).hexdigest() != checksum:
                    errors.append(f"The export bundle hash does not verify for {path}.")
            expected_names = listed_paths | {"export-manifest.json"}
            if set(names) != expected_names:
                errors.append("The export bundle contains unlisted or missing files.")
            required_paths = {
                *(f"artifacts/{filename}" for filename in _REQUIRED_ARTIFACTS.values()),
                "EXPORT-REPORT.txt",
                "PRINT-GUIDANCE.txt",
                "export-manifest.json",
            }
            allowed_paths = required_paths | {
                f"artifacts/{filename}" for filename in _OPTIONAL_ARTIFACTS.values()
            }
            if not required_paths <= set(names) or not set(names) <= allowed_paths:
                errors.append("The export bundle does not use the fixed controlled-export layout.")
    except (OSError, zipfile.BadZipFile):
        return False, ["The export bundle is not a readable ZIP archive."]
    return not errors, errors


def _verify_artifacts(artifacts: list[BundleArtifact]) -> list[BundleArtifact]:
    expected = {**_REQUIRED_ARTIFACTS, **_OPTIONAL_ARTIFACTS}
    by_kind: dict[str, BundleArtifact] = {}
    for artifact in artifacts:
        if artifact.kind not in expected:
            raise ExportBundleError("The candidate includes an undeclared export artifact kind.")
        if artifact.kind in by_kind:
            raise ExportBundleError("The candidate includes duplicate export artifact kinds.")
        if artifact.filename != expected[artifact.kind]:
            raise ExportBundleError(
                "A candidate artifact filename does not match the fixed export layout."
            )
        if len(artifact.content) != artifact.size_bytes:
            raise ExportBundleError("A candidate artifact size does not match immutable metadata.")
        actual_hash = hashlib.sha256(artifact.content).hexdigest()
        if actual_hash != artifact.checksum_sha256:
            raise ExportBundleError("A candidate artifact hash does not match immutable metadata.")
        by_kind[artifact.kind] = artifact
    missing = sorted(set(_REQUIRED_ARTIFACTS) - set(by_kind))
    if missing:
        raise ExportBundleError("The candidate is missing required immutable artifacts.")
    return [by_kind[kind] for kind in sorted(by_kind)]


def _guidance_bytes(print_guidance: dict[str, str]) -> bytes:
    if not print_guidance or not all(
        isinstance(key, str) and isinstance(value, str) and value.strip()
        for key, value in print_guidance.items()
    ):
        raise ExportBundleError("The reviewed template print guidance is unavailable.")
    lines = ["AccessForge print guidance (provisional)", ""]
    for key, value in sorted(print_guidance.items()):
        lines.extend((f"{key.replace('_', ' ').title()}: {value.strip()}", ""))
    lines.extend(
        (
            "This guidance records a reviewed template's stated considerations. It does not ",
            "establish printability, material performance, fit, strength, durability, comfort, ",
            "safety, or suitability for physical use.",
        )
    )
    return "\n".join(lines).encode("utf-8")


def _utf8_text(value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 32 * 1024:
        raise ExportBundleError(f"{label} is unavailable or too large.")
    return (value.strip() + "\n").encode("utf-8")


def _zip_entries(entries: dict[str, bytes]) -> bytes:
    if any(not _safe_zip_path(path) for path in entries):
        raise ExportBundleError("The export bundle layout is unsafe.")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, value in sorted(entries.items()):
            info = zipfile.ZipInfo(filename=path, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, value, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def _safe_zip_path(path: str) -> bool:
    return (
        bool(path)
        and not path.startswith(("/", "\\"))
        and "\\" not in path
        and all(component not in {"", ".", ".."} for component in path.split("/"))
    )
