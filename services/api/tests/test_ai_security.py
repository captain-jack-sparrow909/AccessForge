import base64
import socket

import pytest

from accessforge.ai.security import (
    BaseUrlValidationError,
    CredentialDecryptionError,
    CredentialKeyError,
    credential_fingerprint,
    decrypt_credential,
    encrypt_credential,
    validate_custom_base_url,
)


def encoded_aes_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode("ascii").rstrip("=")


def fake_resolution(*addresses: str):
    def resolve(host: str, port: int, *, type: socket.SocketKind) -> list[tuple[object, ...]]:
        return [
            (socket.AF_INET6 if ":" in address else socket.AF_INET, type, 6, "", (address, port))
            for address in addresses
        ]

    return resolve


def test_aes_gcm_credential_round_trip_uses_random_nonce() -> None:
    key = encoded_aes_key()
    first = encrypt_credential("sk-example-secret-1234", key, "owner-1", "config-1")
    second = encrypt_credential("sk-example-secret-1234", key, "owner-1", "config-1")

    assert first.startswith("afmc1.")
    assert second.startswith("afmc1.")
    assert first != second
    assert "sk-example-secret-1234" not in first
    assert decrypt_credential(first, key, "owner-1", "config-1") == "sk-example-secret-1234"


@pytest.mark.parametrize(
    ("owner_id", "config_id"),
    [("another-owner", "config-1"), ("owner-1", "another-config")],
)
def test_credential_decryption_rejects_mismatched_aad(owner_id: str, config_id: str) -> None:
    key = encoded_aes_key()
    ciphertext = encrypt_credential("sk-example-secret-1234", key, "owner-1", "config-1")

    with pytest.raises(CredentialDecryptionError):
        decrypt_credential(ciphertext, key, owner_id, config_id)


def test_credential_decryption_rejects_tampered_ciphertext_and_wrong_key() -> None:
    key = encoded_aes_key()
    ciphertext = encrypt_credential("sk-example-secret-1234", key, "owner-1", "config-1")
    tampered = f"{ciphertext[:-1]}{'A' if ciphertext[-1] != 'A' else 'B'}"
    wrong_key = base64.urlsafe_b64encode(bytes(range(1, 33))).decode("ascii").rstrip("=")

    with pytest.raises(CredentialDecryptionError):
        decrypt_credential(tampered, key, "owner-1", "config-1")
    with pytest.raises(CredentialDecryptionError):
        decrypt_credential(ciphertext, wrong_key, "owner-1", "config-1")


@pytest.mark.parametrize("key", ["not base64!", "c2hvcnQ", "A" * 44])
def test_credential_encryption_requires_a_valid_256_bit_key(key: str) -> None:
    with pytest.raises(CredentialKeyError):
        encrypt_credential("sk-example-secret-1234", key, "owner-1", "config-1")


def test_credential_fingerprint_is_redacted_and_stable() -> None:
    fingerprint = credential_fingerprint("sk-example-secret-1234")

    assert fingerprint.startswith("sha256:")
    assert fingerprint.endswith("last4:1234")
    assert "sk-example-secret" not in fingerprint
    assert fingerprint == credential_fingerprint("sk-example-secret-1234")


def test_hosted_custom_base_url_requires_public_https_443(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolution("93.184.216.34"))

    assert (
        validate_custom_base_url("https://API.Example.test:443/v1/", allowlist={"api.example.test"})
        == "https://api.example.test:443/v1"
    )

    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url("http://api.example.test", allowlist={"api.example.test"})
    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url("https://api.example.test:8443", allowlist={"api.example.test"})
    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url(
            "https://user:pass@api.example.test", allowlist={"api.example.test"}
        )
    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url(
            "https://api.example.test?token=not-a-secret", allowlist={"api.example.test"}
        )


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.7", "169.254.10.7", "::1", "fc00::1"],
)
def test_hosted_custom_base_url_rejects_non_public_resolutions(
    monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolution(address))

    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url("https://provider.example.test")


def test_hosted_custom_base_url_rejects_localhost_before_resolution() -> None:
    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url("https://localhost")
    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url("https://api.localhost")


def test_hosted_validation_resolves_every_time_to_detect_dns_rebinding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([fake_resolution("93.184.216.34"), fake_resolution("127.0.0.1")])

    def resolve(host: str, port: int, *, type: socket.SocketKind) -> list[tuple[object, ...]]:
        return next(responses)(host, port, type=type)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)

    assert (
        validate_custom_base_url("https://provider.example.test") == "https://provider.example.test"
    )
    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url("https://provider.example.test")


def test_allowlist_is_an_exact_additional_host_restriction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", fake_resolution("93.184.216.34"))

    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url("https://provider.example.test", allowlist={"example.test"})


def test_explicit_unsafe_self_hosted_mode_allows_local_http_endpoint() -> None:
    assert (
        validate_custom_base_url("http://localhost:11434/v1/", allow_unsafe_self_hosted=True)
        == "http://localhost:11434/v1"
    )

    with pytest.raises(BaseUrlValidationError):
        validate_custom_base_url(
            "http://user:pass@localhost:11434/v1", allow_unsafe_self_hosted=True
        )
