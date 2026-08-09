"""A constrained subprocess boundary for trusted CAD compilation.

The subprocess does not execute user/template code.  It receives a DesignSpec
JSON document, resolves a static registry entry, and returns only fixed artifact
names.  It removes secrets and proxy variables, disables Python socket creation
in the child, uses a disposable work directory, and applies OS resource limits
where supported.  A deployment still needs a kernel/container egress policy to
claim complete network isolation; this code intentionally does not overstate
that operational requirement.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from accessforge.cad.compiler import (
    _ARTIFACT_CONTENT_TYPES,
    _ARTIFACT_FILENAMES,
    CadCompilationError,
    CompilationResult,
)
from accessforge.cad.schemas import DesignSpec


class CadIsolationError(CadCompilationError):
    """The isolated compiler did not produce a verifiable bundle."""


@dataclass(frozen=True)
class CadExecutionLimits:
    wall_time_seconds: float = 45.0
    cpu_time_seconds: int = 35
    memory_bytes: int = 1_500_000_000
    file_size_bytes: int = 55_000_000


def _set_resource_limits(limits: CadExecutionLimits) -> None:
    """Best-effort Unix limits; Docker/Render limits remain an operational gate."""

    try:
        import resource

        resource.setrlimit(
            resource.RLIMIT_CPU, (limits.cpu_time_seconds, limits.cpu_time_seconds + 1)
        )
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_size_bytes, limits.file_size_bytes))
        if hasattr(resource, "RLIMIT_AS"):
            resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes))
    except (ImportError, OSError, ValueError):
        # Some developer platforms do not expose all limits.  The worker still
        # has a wall-clock timeout; production isolation is documented separately.
        return


def _compiler_environment(work_directory: Path) -> dict[str, str]:
    path = os.environ.get("PATH", "")
    return {
        "PATH": path,
        "HOME": str(work_directory),
        "TMPDIR": str(work_directory),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "ACCESSFORGE_CAD_NO_NETWORK": "1",
        # VTK/CadQuery can use threading internally; one process and one
        # deterministic thread budget keeps a Celery worker from oversubscribing.
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }


def _json_object(value: object, *, field: str) -> dict[str, object]:
    """Narrow a decoded JSON object before it reaches a trusted result type."""

    if not isinstance(value, dict):
        raise CadIsolationError(f"The compiler result contains an invalid {field} object.")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise CadIsolationError(f"The compiler result contains an invalid {field} key.")
        result[key] = item
    return result


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CadIsolationError(f"The compiler result contains invalid {field}.")
    return list(value)


def _verified_artifact_metadata(
    metadata: Mapping[str, object], artifacts: Mapping[str, bytes]
) -> dict[str, dict[str, object]]:
    """Recompute child-reported fixed artifact metadata from the actual bytes."""

    expected_kinds = set(_ARTIFACT_FILENAMES)
    if set(metadata) != expected_kinds:
        raise CadIsolationError("The compiler result has an invalid artifact metadata set.")
    verified: dict[str, dict[str, object]] = {}
    expected_record_keys = {"filename", "content_type", "size_bytes", "sha256"}
    for kind, filename in _ARTIFACT_FILENAMES.items():
        record = _json_object(metadata.get(kind), field=f"metadata for {kind}")
        if set(record) != expected_record_keys:
            raise CadIsolationError(f"The compiler result has invalid metadata fields for {kind}.")
        content = artifacts[kind]
        expected_content_type = _ARTIFACT_CONTENT_TYPES[kind]
        expected_size = len(content)
        expected_sha256 = hashlib.sha256(content).hexdigest()
        if (
            record.get("filename") != filename
            or record.get("content_type") != expected_content_type
            or isinstance(record.get("size_bytes"), bool)
            or record.get("size_bytes") != expected_size
            or record.get("sha256") != expected_sha256
        ):
            raise CadIsolationError(
                f"The compiler result metadata does not match the fixed {kind} artifact."
            )
        # Return values derived from the verified artifact bytes, never values
        # trusted solely because the isolated child reported them.
        verified[kind] = {
            "filename": filename,
            "content_type": expected_content_type,
            "size_bytes": expected_size,
            "sha256": expected_sha256,
        }
    return verified


def _read_result(output_directory: Path) -> CompilationResult:
    result_path = output_directory / "result.json"
    try:
        raw: object = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CadIsolationError("The compiler did not produce a readable result manifest.") from exc
    result = _json_object(raw, field="manifest")
    artifact_kinds = _string_list(result.get("artifact_kinds"), field="artifact identifiers")
    metadata = _json_object(result.get("artifact_metadata"), field="artifact metadata")
    geometry = _json_object(result.get("geometry_summary"), field="geometry summary")
    validation = _json_object(result.get("validation_report"), field="validation report")
    provenance = _json_object(result.get("provenance"), field="provenance")
    expected_kinds = set(_ARTIFACT_FILENAMES)
    if len(artifact_kinds) != len(expected_kinds) or set(artifact_kinds) != expected_kinds:
        raise CadIsolationError("The compiler did not produce the complete fixed artifact set.")
    artifacts: dict[str, bytes] = {}
    for kind, filename in _ARTIFACT_FILENAMES.items():
        path = (output_directory / filename).resolve()
        if output_directory.resolve() not in path.parents:
            raise CadIsolationError(
                "The compiler attempted to return an artifact outside its workspace."
            )
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise CadIsolationError(f"The compiler artifact {filename} is missing.") from exc
        if len(content) > 50_000_000:
            raise CadIsolationError("The compiler returned an artifact over the output-size limit.")
        artifacts[kind] = content
    return CompilationResult(
        artifacts=artifacts,
        artifact_metadata=_verified_artifact_metadata(metadata, artifacts),
        geometry_summary=geometry,
        validation_report=validation,
        provenance=provenance,
    )


def run_isolated_compilation(
    spec: DesignSpec, limits: CadExecutionLimits | None = None
) -> CompilationResult:
    """Compile a trusted DesignSpec in a short-lived child process."""

    execution_limits = limits or CadExecutionLimits()
    with tempfile.TemporaryDirectory(prefix="accessforge-cad-") as temporary_directory:
        work_directory = Path(temporary_directory)
        input_path = work_directory / "input.json"
        output_directory = work_directory / "output"
        output_directory.mkdir(mode=0o700)
        input_path.write_text(spec.model_dump_json(), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "accessforge.cad.worker_entry",
            str(input_path),
            str(output_directory),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=work_directory,
                env=_compiler_environment(work_directory),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=execution_limits.wall_time_seconds,
                check=False,
                preexec_fn=(lambda: _set_resource_limits(execution_limits))
                if os.name != "nt"
                else None,
            )
        except subprocess.TimeoutExpired as exc:
            raise CadIsolationError("The compiler exceeded its wall-clock time limit.") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            # Do not persist full tool output, which can contain a path or native
            # library internals.  The durable job records a short category instead.
            detail = stderr.splitlines()[-1][:300] if stderr else "unknown compiler failure"
            raise CadIsolationError(f"The compiler failed: {detail}")
        return _read_result(output_directory)
