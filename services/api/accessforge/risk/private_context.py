"""Authenticated private storage for export-time deterministic risk rechecks.

Phase 5 intentionally keeps free text out of the public risk snapshot.  A
Phase 6 recheck must not ask the browser to resubmit that text, so this module
seals the exact typed risk context with AES-256-GCM and binds it to both the
project and immutable risk-assessment ID as associated data.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from accessforge.cad.schemas import canonical_json
from accessforge.risk.schemas import RiskContextInput

RISK_CONTEXT_ENVELOPE_VERSION = "afrc1"
_ENVELOPE_PREFIX = f"{RISK_CONTEXT_ENVELOPE_VERSION}."
_NONCE_BYTES = 12
_AUTH_TAG_BYTES = 16
_AES_256_KEY_BYTES = 32
_MAX_CONTEXT_BYTES = 8 * 1024
_BASE64_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_+/=-]+$")
_BASE64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class RiskContextSealError(ValueError):
    """A context cannot be safely sealed or reopened for deterministic review."""


def context_hash(context: RiskContextInput) -> str:
    return hashlib.sha256(_context_bytes(context)).hexdigest()


def seal_risk_context(
    context: RiskContextInput,
    *,
    key: str,
    project_id: str,
    assessment_id: str,
) -> str:
    """Encrypt a typed context without exposing any of its user-provided text."""

    raw = _context_bytes(context)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    try:
        encrypted = AESGCM(_decode_key(key)).encrypt(
            nonce, raw, _associated_data(project_id, assessment_id)
        )
    except (TypeError, ValueError) as exc:
        raise RiskContextSealError("Risk context sealing failed.") from exc
    payload = nonce + encrypted
    return f"{_ENVELOPE_PREFIX}{base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')}"


def open_risk_context(
    envelope: str,
    *,
    key: str,
    project_id: str,
    assessment_id: str,
) -> RiskContextInput:
    """Authenticate and parse a previously sealed typed risk context."""

    if not isinstance(envelope, str) or not envelope.startswith(_ENVELOPE_PREFIX):
        raise RiskContextSealError("Risk context is unavailable for revalidation.")
    encoded = envelope.removeprefix(_ENVELOPE_PREFIX)
    payload = _decode_envelope(encoded)
    if len(payload) < _NONCE_BYTES + _AUTH_TAG_BYTES:
        raise RiskContextSealError("Risk context is unavailable for revalidation.")
    nonce, encrypted = payload[:_NONCE_BYTES], payload[_NONCE_BYTES:]
    try:
        raw = AESGCM(_decode_key(key)).decrypt(
            nonce, encrypted, _associated_data(project_id, assessment_id)
        )
        decoded = json.loads(raw)
        return RiskContextInput.model_validate(decoded)
    except (InvalidTag, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        raise RiskContextSealError("Risk context is unavailable for revalidation.") from None


def _context_bytes(context: RiskContextInput) -> bytes:
    raw = canonical_json(context.model_dump(mode="json")).encode("utf-8")
    if len(raw) > _MAX_CONTEXT_BYTES:
        raise RiskContextSealError("Risk context is too large to retain for revalidation.")
    return raw


def _associated_data(project_id: str, assessment_id: str) -> bytes:
    if not all(
        isinstance(value, str) and value and len(value) <= 160
        for value in (project_id, assessment_id)
    ):
        raise RiskContextSealError("Risk context lineage is invalid.")
    return canonical_json(
        {
            "assessment_id": assessment_id,
            "project_id": project_id,
            "purpose": "accessforge.risk-context",
            "version": 1,
        }
    ).encode("utf-8")


def _decode_key(value: str) -> bytes:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RiskContextSealError("Risk context encryption is not configured.")
    if not _BASE64_KEY_PATTERN.fullmatch(value) or len(value) % 4 == 1:
        raise RiskContextSealError("Risk context encryption is not configured.")
    try:
        decoded = base64.b64decode(
            value.encode("ascii") + (b"=" * (-len(value) % 4)), altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError) as exc:
        raise RiskContextSealError("Risk context encryption is not configured.") from exc
    if len(decoded) != _AES_256_KEY_BYTES:
        raise RiskContextSealError("Risk context encryption is not configured.")
    return decoded


def _decode_envelope(encoded: str) -> bytes:
    if not encoded or not _BASE64URL_PATTERN.fullmatch(encoded) or len(encoded) % 4 == 1:
        raise RiskContextSealError("Risk context is unavailable for revalidation.")
    try:
        payload = base64.urlsafe_b64decode(encoded.encode("ascii") + (b"=" * (-len(encoded) % 4)))
    except (binascii.Error, ValueError) as exc:
        raise RiskContextSealError("Risk context is unavailable for revalidation.") from exc
    if base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=") != encoded:
        raise RiskContextSealError("Risk context is unavailable for revalidation.")
    return payload
