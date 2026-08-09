# Local development

## Prerequisites

- Node.js 20.9+, pnpm 11+, Python 3.12–3.14, uv 0.9+, Docker, and OpenSSL.

## First-time setup

```bash
pnpm install
uv sync --project services/api
pnpm dev:keys
pnpm generate:api
docker compose up -d postgres redis minio
```

`pnpm dev:keys` writes only gitignored local files: `.env` for Compose’s public key and `apps/web/.env.local` for development auth/private signing key. The local account is `demo@accessforge.local` / `accessforge-local-only`.

## Run services

```bash
docker compose up --build api worker
```

In another terminal:

```bash
pnpm dev
```

Open `http://localhost:3000`, choose the local development account, and start a guided project. The browser receives only a short-lived backend token; it never receives the signing key.

The Phase 2 workflow is deliberately consent-first:

1. Describe the goal, object, action, environment, and scope questions.
2. Record separate choices for text, still images, video, helper access, future provider sharing, community publishing, and future contact.
3. Use text-only observation, upload an allowlisted still/video through a short-lived presigned URL, or skip capture.
4. Add manual measurements in `mm`, `cm`, or `in`, with method, tolerance, unknown status, and confirmation.

The direct upload endpoint checks the allowlisted media type and size before issuing a URL. The API creates the configured private MinIO bucket on first presign in local development. Completion verifies the object-store metadata and quarantines expired or mismatched uploads. A worker later processes queued project deletion and expired pending uploads.

## Optional Phase 3 model-provider setup

AI is off by default. Do not add a provider key just to run the deterministic
project, consent, capture, and measurement workflows. Leave
`DEFAULT_MODEL_PROVIDER=none` unless this local deployment intentionally uses a
deployment-managed provider.

All provider configuration belongs to the API environment, never to
`apps/web/.env.local` or any `NEXT_PUBLIC_*` variable. For Docker Compose, add
the API variables to the repository-root `.env` that `pnpm dev:keys` creates.
For an API started from inside `services/api`, use the same values in
`services/api/.env`; otherwise use the root `.env` or export them in the shell.
`services/api/.env.example` documents every supported name. Generate a local
encryption key with:

```bash
openssl rand -base64 32
```

When updating an existing local database, run `uv run --project services/api alembic upgrade head` before starting the API. `AUTO_CREATE_DB=true` creates
missing development tables but does not alter an existing schema; the API
container runs the same migration command before Uvicorn starts.

Paste the generated value into `MODEL_CREDENTIAL_ENCRYPTION_KEY` in
the API environment if you will save a local BYOK configuration. It must decode
to exactly 32 bytes. The API encrypts the personal key with AES-256-GCM and
binds it to the owner and provider-configuration IDs; list responses contain
only a non-sensitive fingerprint. Do not commit either key, echo it in issue
logs, or place it in the frontend environment.

For a deployment-managed local provider, set only the appropriate backend
variables, for example `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE`, and model IDs.
The other supported production adapter families use `OPENAI_*`, `ANTHROPIC_*`,
and `GOOGLE_*` variables. Configuration names and safe defaults are documented
in `services/api/.env.example`.

Use the **Model settings** page to create, capability-test, select, or revoke a
configuration. A provider test is a low-cost request and can incur vendor cost;
it is not required for local deterministic tests. The `fake` /
`development_fake` option is available only when `APP_ENV=development`. It is
offline, deterministic, and suitable for the requirements-flow and provider
contract tests; it must never be enabled in a hosted production environment.

The settings page can also store the current input and output USD-per-million
token rates for that configuration. Those optional rates let AccessForge retain
an estimate with a completed run; leave them blank when the vendor's model
pricing is unknown rather than relying on a hard-coded price.

An external provider call additionally needs a live `ai_provider_sharing`
consent record on the project. Phase 3 sends only the selected minimum derived
project text and/or measurements. It never sends raw source images, video,
audio, object-store URLs, or other media bytes to a provider, even if media
capture consent exists. Requirements remain editable proposals with source
provenance until the participant confirms a revision.

For a custom OpenAI-compatible endpoint, hosted deployments require an HTTPS
endpoint on a public host and port 443. URL credentials, query strings,
fragments, redirects, and private/loopback/link-local targets are rejected. A
self-hosted operator may set `ALLOW_UNSAFE_CUSTOM_MODEL_ENDPOINTS=true` only
after accepting that SSRF protection is relaxed; use
`CUSTOM_MODEL_ENDPOINT_ALLOWLIST` to retain an explicit hostname restriction.
See [ADR-0007](../architecture/ADR-0007-model-provider-boundary.md) for the
full provider, data, and credential boundary.

## Phase 4 CAD foundation

Phase 4 ships only three fixed, repository-owned template releases and accepts
only an immutable, unit-bearing DesignSpec. The normal project candidate route
is deliberately unavailable until Phase 5 records a deterministic R1 decision
with no unresolved assumptions. Do not change a project state manually to try
to exercise compilation.

The deterministic compiler is exercised with synthetic repository fixtures:

```bash
uv run --project services/api pytest services/api/tests/test_cad_engine.py
```

The worker uses a disposable subprocess workspace, fixed artifact names,
resource limits where the host supports them, and Python-level socket blocking.
Those controls are not an enforceable deployed no-egress boundary: the current
Compose and Render worker have normal network access. Do not feed real-user
data into a CAD job, treat a preview as a physical-fit result, or make a
physical output claim from this environment. See
[ADR-0005](../architecture/ADR-0005-cad-engine.md) for the full boundary.

## Phase 5 deterministic risk and private comparison

Phase 5 adds a versioned deterministic R0–R3 review at
`/projects/:projectId/risk`. For synthetic development only, create a confirmed
requirements revision and DesignSpec, record every risk-context field, then
read the server's current decision. Only a current R1 decision that explicitly
permits private generation can create a bounded plan.

The preferred plan path presents two or three reviewed-template variants at a
waiting-for-user checkpoint. Choosing **Queue private comparison** creates a
durable private batch; it does not grant approval, export, manufacture, or
physical-use permission. The comparison view reports tradeoffs, compiler state,
deterministic validation state, and unknown or unassessed properties. A later
selection is for software review only.

Queued job rows are the durable dispatch record. When a Celery beat process is
configured, the API's periodic recovery task republishes queued candidate IDs
and terminally resolves stale worker claims. This source-level behavior has
only been verified with synthetic SQLite fixtures. Do not treat it as evidence
of deployed Redis/Celery/PostgreSQL recovery, no-egress isolation, fit,
printability, material suitability, safety, or any physical outcome. See
[ADR-0008](../architecture/ADR-0008-phase5-risk-and-comparison.md) for the
complete boundary.

## Checks

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
pnpm lint
pnpm typecheck
pnpm build
uv run --project services/api pytest
uv run --project services/api pytest services/api/tests/test_ai_providers.py services/api/tests/test_ai_security.py
```

## Current limitations

The Phase 3 AI workflow is limited to requirements extraction and clarification.
Phase 4 adds synthetic fixture geometry and Phase 5 adds deterministic risk and
private software comparison only; neither approves outputs, establishes
fit/strength/printability/material behavior, or claims safety. Phase 6 still
owns controlled physical work, approval, and export. Malware scanning,
browser-level capture verification, deployment-grade no-egress isolation, and
hosted queue recovery are also incomplete. The local API tests use an isolated
SQLite database; a running MinIO/Postgres/Redis stack is still required to
verify the full direct-upload, private-artifact, deletion-worker, and
comparison-worker runtime. Do not put real participant data into this
environment or use real provider keys before the required privacy, safety,
accessibility, and lived-experience review.
