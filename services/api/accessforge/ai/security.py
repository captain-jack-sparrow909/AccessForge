"""Security primitives for model-provider credentials and custom endpoints.

This module deliberately has no database or HTTP-client dependency.  Callers should
validate a custom endpoint when it is saved *and again immediately before every
outbound connection*.  The latter check makes a DNS rebinding attack fail closed
as long as the provider transport does not follow redirects.

The functions here never log credentials and only return redacted credential
metadata.  Plaintext credentials should be kept in scope only for the outbound
provider call that needs them.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import json
import re
import secrets
import socket
from collections.abc import Iterable
from urllib.parse import SplitResult, urlsplit, urlunsplit

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_CREDENTIAL_ENVELOPE_VERSION = "afmc1"
_CREDENTIAL_ENVELOPE_PREFIX = f"{_CREDENTIAL_ENVELOPE_VERSION}."
_NONCE_BYTES = 12
_AUTH_TAG_BYTES = 16
_AES_256_KEY_BYTES = 32
_MAX_CREDENTIAL_BYTES = 16 * 1024
_MAX_IDENTIFIER_CHARS = 512
_MAX_URL_CHARS = 2_048
_HOSTED_ALLOWED_PORTS = frozenset({443})
_BASE64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_BASE64_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_+/=-]+$")


class CredentialSecurityError(ValueError):
    """Base error for credential handling failures without secret detail."""


class CredentialKeyError(CredentialSecurityError):
    """Raised when the master encryption key is absent or invalid."""


class CredentialEncryptionError(CredentialSecurityError):
    """Raised when a credential cannot be encrypted."""


class CredentialDecryptionError(CredentialSecurityError):
    """Raised when a credential envelope cannot be authenticated or decoded."""


class BaseUrlValidationError(CredentialSecurityError):
    """Raised when a custom provider endpoint is unsafe or malformed."""


def encrypt_credential(plaintext: str, key: str, owner_id: str, config_id: str) -> str:
    """Encrypt a BYOK credential using AES-256-GCM.

    ``key`` must be a base64 or base64url encoded 32-byte value.  The returned
    versioned envelope contains a random 96-bit nonce plus ciphertext and GCM tag;
    neither the owner nor provider-config identifier is stored in the envelope.
    Those identifiers are authenticated associated data, so a credential cannot be
    moved to a different owner or configuration and still decrypt.
    """

    secret = _validate_credential_plaintext(plaintext)
    aad = _credential_aad(owner_id, config_id)
    encryption_key = _decode_encryption_key(key)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    try:
        encrypted = AESGCM(encryption_key).encrypt(nonce, secret.encode("utf-8"), aad)
    except (TypeError, ValueError) as exc:
        raise CredentialEncryptionError("Credential encryption failed.") from exc
    payload = nonce + encrypted
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{_CREDENTIAL_ENVELOPE_PREFIX}{encoded}"


def decrypt_credential(ciphertext: str, key: str, owner_id: str, config_id: str) -> str:
    """Authenticate and decrypt a credential envelope produced by this module.

    Incorrect keys, tampered envelopes, and mismatched owner/config identifiers all
    raise the same generic :class:`CredentialDecryptionError` so callers do not get
    an oracle about the plaintext or its associated data.
    """

    if not isinstance(ciphertext, str) or not ciphertext.startswith(_CREDENTIAL_ENVELOPE_PREFIX):
        raise CredentialDecryptionError("Credential envelope has an unsupported format.")
    encoded = ciphertext.removeprefix(_CREDENTIAL_ENVELOPE_PREFIX)
    payload = _decode_envelope_payload(encoded)
    if len(payload) < _NONCE_BYTES + _AUTH_TAG_BYTES:
        raise CredentialDecryptionError("Credential envelope is malformed.")

    aad = _credential_aad(owner_id, config_id)
    encryption_key = _decode_encryption_key(key)
    nonce, encrypted = payload[:_NONCE_BYTES], payload[_NONCE_BYTES:]
    try:
        plaintext = AESGCM(encryption_key).decrypt(nonce, encrypted, aad)
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError, ValueError, TypeError):
        raise CredentialDecryptionError("Credential could not be authenticated.") from None


def credential_fingerprint(plaintext: str) -> str:
    """Return a stable, redacted display value for a credential.

    The value intentionally contains only the first 16 hexadecimal characters of a
    SHA-256 digest and the final four printable characters.  It is appropriate for
    configuration lists and audit displays, never for authentication.
    """

    secret = _validate_credential_plaintext(plaintext)
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]
    suffix = secret[-4:]
    safe_suffix = suffix if suffix.isprintable() else "hidden"
    return f"sha256:{digest}:last4:{safe_suffix}"


def validate_custom_base_url(
    url: str,
    *,
    allow_unsafe_self_hosted: bool = False,
    allowlist: set[str] | None = None,
) -> str:
    """Validate and canonicalize a custom OpenAI-compatible base URL.

    In hosted mode (the default), an endpoint must use HTTPS on port 443 and resolve
    exclusively to globally routable addresses.  URLs with credentials, queries, or
    fragments are rejected so endpoint settings cannot become another credential
    channel.  ``allowlist`` applies exact hostname matching after IDNA normalization.

    Setting ``allow_unsafe_self_hosted=True`` is intentionally explicit and is for a
    self-hosted deployment operator who accepts the SSRF risk of local/private HTTP
    endpoints.  It relaxes scheme, port, and address checks, but it never permits URL
    credentials.  A supplied allowlist remains an additional restriction in either
    mode.

    Call this function immediately before each outbound provider connection as well
    as when saving the configuration.  It resolves hostnames on every hosted-mode
    invocation to make DNS rebinding checks fail closed.
    """

    parts = _parse_base_url(url)
    scheme = parts.scheme.lower()
    allowed_schemes = {"http", "https"} if allow_unsafe_self_hosted else {"https"}
    if scheme not in allowed_schemes:
        if allow_unsafe_self_hosted:
            raise BaseUrlValidationError("Custom base URLs must use HTTP or HTTPS.")
        raise BaseUrlValidationError("Hosted custom base URLs must use HTTPS.")

    if parts.username is not None or parts.password is not None:
        raise BaseUrlValidationError("Custom base URLs must not contain credentials.")
    if parts.query or parts.fragment:
        raise BaseUrlValidationError("Custom base URLs must not include query or fragment data.")

    hostname = parts.hostname
    if hostname is None:
        raise BaseUrlValidationError("Custom base URLs must include a hostname.")
    normalized_host = _normalize_hostname(hostname)

    try:
        port = parts.port
    except ValueError as exc:
        raise BaseUrlValidationError("Custom base URL has an invalid port.") from exc
    effective_port = port if port is not None else (443 if scheme == "https" else 80)

    normalized_allowlist = _normalize_allowlist(allowlist)
    if normalized_allowlist is not None and normalized_host not in normalized_allowlist:
        raise BaseUrlValidationError("Custom base URL hostname is not on the allowlist.")

    if not allow_unsafe_self_hosted:
        if normalized_host == "localhost" or normalized_host.endswith(".localhost"):
            raise BaseUrlValidationError("Hosted custom base URLs cannot target localhost.")
        if port is not None and effective_port not in _HOSTED_ALLOWED_PORTS:
            raise BaseUrlValidationError("Hosted custom base URLs must use port 443.")
        _validate_hosted_network_target(normalized_host, effective_port)

    return _canonical_base_url(parts, normalized_host, port)


def _validate_credential_plaintext(plaintext: str) -> str:
    if not isinstance(plaintext, str) or not plaintext:
        raise CredentialEncryptionError("Credential must be a non-empty string.")
    if len(plaintext.encode("utf-8")) > _MAX_CREDENTIAL_BYTES:
        raise CredentialEncryptionError("Credential exceeds the maximum permitted size.")
    return plaintext


def _credential_aad(owner_id: str, config_id: str) -> bytes:
    owner = _validate_identifier(owner_id, "owner ID")
    config = _validate_identifier(config_id, "provider configuration ID")
    payload = {
        "config_id": config,
        "owner_id": owner,
        "purpose": "accessforge.model-credential",
        "version": 1,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CredentialEncryptionError(f"{field_name} must be a non-empty trimmed string.")
    if len(value) > _MAX_IDENTIFIER_CHARS:
        raise CredentialEncryptionError(f"{field_name} exceeds the maximum permitted length.")
    return value


def _decode_encryption_key(key: str) -> bytes:
    """Decode a base64/base64url master key and require exactly 256 bits."""

    if not isinstance(key, str) or not key or key != key.strip():
        raise CredentialKeyError("Credential encryption key must be a non-empty base64 string.")
    if not _BASE64_KEY_PATTERN.fullmatch(key) or len(key) % 4 == 1:
        raise CredentialKeyError("Credential encryption key must be valid base64.")
    encoded = key.encode("ascii")
    padded = encoded + (b"=" * (-len(encoded) % 4))
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CredentialKeyError("Credential encryption key must be valid base64.") from exc
    if len(decoded) != _AES_256_KEY_BYTES:
        raise CredentialKeyError("Credential encryption key must decode to exactly 32 bytes.")
    return decoded


def _decode_envelope_payload(encoded: str) -> bytes:
    if not encoded or not _BASE64URL_PATTERN.fullmatch(encoded) or len(encoded) % 4 == 1:
        raise CredentialDecryptionError("Credential envelope is malformed.")
    padded = encoded + ("=" * (-len(encoded) % 4))
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError) as exc:
        raise CredentialDecryptionError("Credential envelope is malformed.") from exc
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    if canonical != encoded:
        raise CredentialDecryptionError("Credential envelope is malformed.")
    return decoded


def _parse_base_url(url: str) -> SplitResult:
    if not isinstance(url, str) or not url or len(url) > _MAX_URL_CHARS:
        raise BaseUrlValidationError("Custom base URL is missing or too long.")
    if any(ord(character) <= 0x20 or ord(character) == 0x7F for character in url):
        raise BaseUrlValidationError(
            "Custom base URL must not contain whitespace or control characters."
        )
    if "\\" in url:
        raise BaseUrlValidationError("Custom base URL must not contain backslashes.")
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise BaseUrlValidationError("Custom base URL is malformed.") from exc
    if not parts.scheme or not parts.netloc:
        raise BaseUrlValidationError("Custom base URL must be absolute.")
    return parts


def _normalize_hostname(hostname: str) -> str:
    normalized = hostname.rstrip(".").lower()
    if not normalized or len(normalized) > 253 or "%" in normalized:
        raise BaseUrlValidationError("Custom base URL hostname is invalid.")
    try:
        return ipaddress.ip_address(normalized).compressed
    except ValueError:
        pass
    try:
        ascii_host = normalized.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise BaseUrlValidationError("Custom base URL hostname is invalid.") from exc
    if not ascii_host or any(label == "" for label in ascii_host.split(".")):
        raise BaseUrlValidationError("Custom base URL hostname is invalid.")
    return ascii_host


def _normalize_allowlist(allowlist: set[str] | None) -> set[str] | None:
    if allowlist is None:
        return None
    normalized: set[str] = set()
    for entry in allowlist:
        if not isinstance(entry, str):
            raise BaseUrlValidationError("Custom base URL allowlist contains an invalid hostname.")
        normalized.add(_normalize_hostname(entry))
    return normalized


def _validate_hosted_network_target(hostname: str, port: int) -> None:
    """Resolve a target and reject every address that is not public internet space."""

    try:
        literal_address = ipaddress.ip_address(hostname)
    except ValueError:
        literal_address = None

    if literal_address is not None:
        _reject_non_public_address(literal_address)
        return

    try:
        resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise BaseUrlValidationError("Custom base URL hostname could not be resolved.") from exc
    if not resolved:
        raise BaseUrlValidationError("Custom base URL hostname did not resolve to an address.")

    addresses = _resolved_ip_addresses(resolved)
    if not addresses:
        raise BaseUrlValidationError("Custom base URL hostname did not resolve to an IP address.")
    for address in addresses:
        _reject_non_public_address(address)


def _resolved_ip_addresses(
    resolved: Iterable[tuple[object, object, object, object, tuple[object, ...]]],
) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for result in resolved:
        sockaddr = result[4]
        if not sockaddr or not isinstance(sockaddr[0], str):
            raise BaseUrlValidationError("Custom base URL hostname resolved to an invalid address.")
        raw_address = sockaddr[0].split("%", 1)[0]
        try:
            addresses.add(ipaddress.ip_address(raw_address))
        except ValueError as exc:
            raise BaseUrlValidationError(
                "Custom base URL hostname resolved to an invalid address."
            ) from exc
    return addresses


def _reject_non_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
        or address.is_reserved
        or not address.is_global
    ):
        raise BaseUrlValidationError("Hosted custom base URLs must resolve to public addresses.")


def _canonical_base_url(parts: SplitResult, hostname: str, port: int | None) -> str:
    host_for_url = f"[{hostname}]" if ":" in hostname else hostname
    authority = f"{host_for_url}:{port}" if port is not None else host_for_url
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), authority, path, "", ""))
