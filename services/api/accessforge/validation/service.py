"""Phase 5 validation policy around immutable compiler reports.

The CAD compiler's Phase 4 checks remain authoritative for their own measured
values.  This module normalizes them into a versioned decision record and keeps
every `not_assessed` finding visible instead of upgrading it to a pass.
"""

from __future__ import annotations

from typing import Literal

from accessforge.cad.schemas import canonical_hash

VALIDATOR_VERSION = "phase5-deterministic-validation.v1"
VALIDATOR_HASH = canonical_hash(
    {
        "version": VALIDATOR_VERSION,
        "failure_statuses": ["failed", "error"],
        "incomplete_statuses": ["needs_confirmation", "not_assessed"],
        "phase6_export": "always_blocked_until_explicit_approval_and_validation",
    }
)

ValidationOverallStatus = Literal["passed", "failed", "needs_confirmation"]


def normalize_validation_report(
    report: dict[str, object], *, risk_assessment_id: str
) -> tuple[dict[str, object], ValidationOverallStatus]:
    """Add Phase 5 lineage and classify known versus unassessed findings."""

    source_findings = report.get("findings")
    if not isinstance(source_findings, list):
        return _malformed_report(risk_assessment_id)
    findings: list[dict[str, object]] = []
    for item in source_findings:
        if not isinstance(item, dict):
            return _malformed_report(risk_assessment_id)
        normalized = _normalized_finding(item)
        if normalized is None:
            return _malformed_report(risk_assessment_id)
        findings.append(normalized)
    findings.append(
        {
            "check_id": "current-risk-assessment",
            "check_version": VALIDATOR_VERSION,
            "status": "passed",
            "severity": "info",
            "measured_value": risk_assessment_id,
            "threshold": "current R1 decision",
            "unit": None,
            "evidence": {"risk_assessment_id": risk_assessment_id},
            "plain_language_explanation": (
                "The candidate was queued from the current deterministic R1 risk decision."
            ),
            "remediation": None,
        }
    )
    statuses = {str(finding["status"]) for finding in findings}
    overall: ValidationOverallStatus
    if statuses & {"failed", "error"}:
        overall = "failed"
    elif statuses & {"needs_confirmation", "not_assessed"}:
        overall = "needs_confirmation"
    else:
        overall = "passed"
    normalized_report: dict[str, object] = {
        "report_schema_version": "1.0",
        "report_type": "phase5_deterministic_validation",
        "validator_version": VALIDATOR_VERSION,
        "validator_hash": VALIDATOR_HASH,
        "overall_status": overall,
        "findings": findings,
        "limitations": (
            "This report records deterministic software checks and their gaps. It does not "
            "approve manufacture, export, physical use, fit, safety, strength, printability, "
            "or an accessibility outcome."
        ),
    }
    return normalized_report, overall


def validation_allows_phase6_export(report: dict[str, object]) -> tuple[bool, list[str]]:
    """Shared future gate: Phase 5 intentionally has no approval or export path."""

    reasons = ["Phase 6 approval and controlled physical-validation gates are not implemented."]
    status = report.get("overall_status")
    if status != "passed":
        reasons.append(
            "Deterministic validation contains failed, unassessed, or confirmation-needed checks."
        )
    return False, reasons


def validation_limitations(report: dict[str, object] | None) -> list[str]:
    """Return concise, typed display text for checks that remain unassessed.

    This is derived from the immutable validation report rather than authored
    by the browser, so a comparison cannot hide a deterministic limitation.
    """

    if report is None:
        return []
    findings = report.get("findings")
    if not isinstance(findings, list):
        return []
    limitations: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        if finding.get("status") not in {"needs_confirmation", "not_assessed"}:
            continue
        explanation = finding.get("plain_language_explanation")
        if isinstance(explanation, str) and explanation.strip():
            limitations.append(explanation.strip())
    return list(dict.fromkeys(limitations))


def _normalized_finding(item: dict[object, object]) -> dict[str, object] | None:
    required = {
        "check_id",
        "check_version",
        "status",
        "severity",
        "measured_value",
        "threshold",
        "unit",
        "evidence",
        "plain_language_explanation",
        "remediation",
    }
    if set(item) != required:
        return None
    if not all(
        isinstance(item[key], str) for key in ("check_id", "check_version", "status", "severity")
    ):
        return None
    if not isinstance(item["evidence"], dict):
        return None
    if not isinstance(item["plain_language_explanation"], str):
        return None
    remediation = item["remediation"]
    if remediation is not None and not isinstance(remediation, str):
        return None
    unit = item["unit"]
    if unit is not None and not isinstance(unit, str):
        return None
    return {str(key): value for key, value in item.items()}


def _malformed_report(risk_assessment_id: str) -> tuple[dict[str, object], ValidationOverallStatus]:
    report: dict[str, object] = {
        "report_schema_version": "1.0",
        "report_type": "phase5_deterministic_validation",
        "validator_version": VALIDATOR_VERSION,
        "validator_hash": VALIDATOR_HASH,
        "overall_status": "failed",
        "findings": [
            {
                "check_id": "validation-report-schema",
                "check_version": VALIDATOR_VERSION,
                "status": "error",
                "severity": "error",
                "measured_value": None,
                "threshold": "complete Phase 4 finding schema",
                "unit": None,
                "evidence": {"risk_assessment_id": risk_assessment_id},
                "plain_language_explanation": (
                    "The compiler validation report could not be safely interpreted."
                ),
                "remediation": "Do not approve or export this candidate; inspect the compiler run.",
            }
        ],
        "limitations": "A malformed validation report is not an acceptable candidate result.",
    }
    return report, "failed"
