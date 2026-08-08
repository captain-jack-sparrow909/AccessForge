# ADR-0007: Vendor-neutral model-provider boundary

Status: proposed  
Date: 2026-08-08

## Context

AccessForge can use a language model to organize a participant's confirmed text
and measurements into an editable requirements draft. That is useful only when
it remains optional, auditable, and independent of any one vendor. The product
also handles sensitive project information, so a provider integration must not
turn model selection into an uncontrolled data-export or credential-management
path.

Phase 3 introduces this boundary for requirements extraction and clarification
planning only. It does not introduce model-generated geometry, model-controlled
risk decisions, or model access to project media.

## Decision

### Provider contract and selection

- Domain workflows depend on a small, typed `ModelProvider` contract for text
  completion, schema-validated structured completion, and capability probes.
- Built-in adapters cover DeepSeek, OpenAI-compatible endpoints, OpenAI,
  Anthropic, and Google/Gemini. An offline fake adapter is available only in a
  local development environment and contract tests.
- A project explicitly selects a saved provider configuration. The selected
  configuration, provider, model, prompt version/hash, safe content hashes,
  token usage, latency, status, and sanitized error category are recorded with
  the resulting agent run.
- Capability probes report confirmed, unsupported, or unknown states. A
  workflow must use a confirmed capability or stop with an actionable message;
  it must not silently substitute a vendor or model.
- AI remains disabled unless a provider configuration is deliberately created.
  Manual, deterministic project, consent, capture, measurement, and later
  deterministic safety/CAD workflows continue to work without a provider key.

### Data, consent, and output boundary

- An external provider call requires a separate active
  `ai_provider_sharing` consent record in addition to the configuration's
  selected data categories.
- Phase 3 sends only the minimum project text and/or measurements selected by
  the user, including each measurement's explicit confirmation or unknown
  state. **Raw source images, video, audio, object-store URLs,
  and other media bytes are never sent to a model provider in this phase.**
- Project text is explicitly delimited as untrusted data. Instructions found
  inside observations or other project content cannot change workflow rules.
- Model output is parsed into Pydantic/JSON-schema contracts, checked against
  the source identifiers supplied in the context, and rejected before it can
  become a domain requirement. It is always an editable proposal, not a fact.
- The assistant may not create geometry, execute code, select an unreviewed
  template, lower risk, suppress validation findings, approve an output, or
  export an artifact. User confirmation and deterministic workflows own those
  decisions.
- Private chain-of-thought or reasoning traces are neither requested for
  storage nor displayed. AccessForge keeps concise user-facing rationale and
  structured, provenance-bearing output instead.

### Credentials and network controls

- Deployment-managed keys live only in the Render API/worker secret
  environments. They are not exposed to Vercel, browser code, Docker build
  arguments, logs, telemetry, or the checked-in environment template.
- A bring-your-own key is sent once to the backend over TLS and encrypted at
  rest with AES-256-GCM. A random nonce is used and authenticated associated
  data binds the ciphertext to its owner and provider-configuration IDs.
  Listings expose only a non-sensitive fingerprint; revocation clears the
  encrypted credential.
- `MODEL_CREDENTIAL_ENCRYPTION_KEY` is a backend-only, base64-encoded 32-byte
  master key. It supports future rotation; it is never a browser variable.
- Custom OpenAI-compatible endpoints are treated as an SSRF boundary. Hosted
  deployments require HTTPS, no URL credentials/query/fragment, port 443, and
  a publicly routable hostname. Addresses are resolved and checked when saved
  and again before connection; redirects are disabled. Operators may relax
  this only for an explicitly self-hosted deployment with
  `ALLOW_UNSAFE_CUSTOM_MODEL_ENDPOINTS=true`, preferably with a hostname
  allowlist.

## Alternatives considered

- A direct DeepSeek-only integration: quick initially, but hard-codes provider
  semantics into domain workflows and makes user-controlled alternatives
  difficult.
- Calling providers from Vercel/browser code: would expose credentials and
  make project-data consent and audit controls unreliable.
- Storing personal keys unencrypted or as third-party secret references only:
  the former is unacceptable; the latter prevents a portable open-source
  self-hosted deployment.
- Sending raw media by default: it expands privacy exposure and is unnecessary
  for the Phase 3 text-and-measurement requirements workflow.

## Consequences

Positive:

- users can choose a compatible provider without changing requirements-domain
  code
- no provider is required for core deterministic workflows
- every AI inference is attributable, inspectable, editable, and confirmable
- credentials and custom endpoints have clear ownership and security controls

Costs:

- adapters need a shared contract suite and provider-specific maintenance
- capability probes and provider calls can fail, cost money, or add latency
- hosted deployments must manage encryption keys, egress policy, and explicit
  consent lifecycle correctly

## Operational requirements

- Keep all real provider keys in backend secret stores. Configure no provider
  key in `NEXT_PUBLIC_*` variables or Vercel settings.
- Set `DEFAULT_MODEL_PROVIDER=none` unless a deployment intentionally enables
  a managed provider. A configured managed key does not bypass per-project
  consent.
- Use `fake` with `development_fake` only in `APP_ENV=development`; production
  rejects it. It exists for deterministic local tests, not as a fallback for a
  failed external provider.
- Add any new adapter behind the shared provider contract tests. It must return
  conservative capabilities, validate structured output, redact errors, avoid
  retaining credentials, and preserve the text-only boundary.
