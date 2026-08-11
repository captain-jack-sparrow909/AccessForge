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

## Phase 6 controlled-export source boundary

The `/projects/:projectId/export` page exposes a server-owned, default-denied
readiness result, exact-revision acknowledgement, private feedback, and a
potential-hazard reporting path. It must be used with synthetic data only.
An acknowledgement is not professional approval, a safety result, a fit result,
a manufacturing authorization, or permission for human physical use.

`RISK_CONTEXT_ENCRYPTION_KEY` must be a backend-only base64-encoded 32-byte
key if the server is ever expected to replay a sealed risk context. Leaving it
unset makes the Phase 6 recheck fail closed. Keep
`PHASE6_CONTROLLED_VALIDATION_ENABLED=false` and
`PHASE6_EXPORT_ENABLED=false`: setting either true does not approve a release
and is not supported for ordinary local development. The current template
releases have no independently reviewed release controls or non-human evidence
and therefore remain blocked even if an operator changes a flag.

The current protocol schema records only reviewer-entered hashes plus
non-human dimensional-fixture/coupon observations. It accepts no evidence
upload, does no scanning, and cannot establish fit, comfort, safety, strength,
durability, printability, material performance, or physical suitability. Use
the potential-hazard path to stop a candidate's current export path; it is a
private report, not a diagnosis or a global recall notification system.

When the future gate is independently approved, bundle bytes are delivered
through an authenticated no-store API response after a fresh server recheck.
AccessForge does not return an object-store presigned bearer URL for a Phase 6
bundle, so a later hazard, evidence/control change, or policy disablement
blocks future download requests. Bytes already delivered to a browser cannot
be recalled.

## Phase 7 accessibility and reliability source boundary

Phase 7 source work does not complete an accessibility audit, a participant
pilot, a security review, or a deployment/recovery drill. Keep all project data
synthetic while validating this foundation.

The local Compose file now declares a separate `scheduler` service for Celery
beat. It schedules the durable deletion outbox and CAD recovery every minute;
workers remain separately scalable. The schedule file is ephemeral, while
deletion state belongs in the database. This configuration has not been
exercised against the local Docker runtime in this environment.

After a project is soft-deleted, ordinary project routes hide it immediately.
Its owner can retrieve only sanitized cleanup progress from:

```bash
curl -H "Authorization: Bearer <short-lived-backend-token>" \
  http://localhost:8000/v1/projects/<project-id>/deletion-status
```

The status exposes an opaque error category, attempt count, lease/retry times,
two-pass reconciliation progress, and terminal status; it never returns raw
object-store errors, object keys, credentials, or the requester identity.
Deletion first fences queued/running CAD work on the project row. Cleanup then
waits for every issued direct-upload authorization to expire plus a settlement
window, waits for server-side CAD work to quiesce, deletes known metadata keys,
and reconciles every object under the fixed `private/<project-id>/` prefix. It
requires two complete empty prefix inventories separated in time before it can
report success. A late object resets that confirmation sequence.

Storage cleanup retries with bounded backoff. An incomplete/bounded prefix
inventory or a defensive SDK-operation timeout goes directly to
`manual_review_required`; neither path is allowed to claim success. The timeout
path is deliberately not requeued because the underlying SDK thread may still
be in flight. The deployed object-store identity therefore needs paginated
list and delete permission on only the private project prefix as well as the
existing object operations. Do not change a row directly to mark deletion
complete; follow the unexercised, synthetic-only [deletion and recovery
runbook](runbooks/deletion-recovery.md) once an owner approves an isolated
drill.

The optional 3D preview is intentionally not part of the primary candidate
review path. Use the structured report without opening it. Source-level web
checks are documented in the
[Phase 7 accessibility baseline](../accessibility/phase7-source-baseline.md);
they do not replace browser, assistive-technology, low-end-device, or
participant testing. The [Phase 7 performance budgets](../performance/phase7-budgets.md)
define the future low-end and slow-network release evidence without claiming
that a browser or real-device pass has occurred.

## Checks

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
pnpm lint
pnpm typecheck
pnpm build
uv run --project services/api pytest
uv run --project services/api pytest services/api/tests/test_ai_providers.py services/api/tests/test_ai_security.py
uv run --project services/api pytest services/api/tests/test_phase7_deletion_recovery.py
pnpm --filter @accessforge/web test
```

## Current limitations

The Phase 3 AI workflow is limited to requirements extraction and clarification.
Phase 4 adds synthetic fixture geometry, Phase 5 adds deterministic risk and
private software comparison, Phase 6 adds default-denied export records, and
Phase 7 adds source-level accessibility/reliability safeguards only; none
approve outputs, establish fit/strength/printability/material behavior, claim
safety, claim accessibility conformance, or demonstrate recovery. Malware
scanning, evidence-upload verification, browser-level capture verification,
deployment-grade no-egress isolation, browser/assistive-technology testing,
participant pilot work, backup/restore evidence, and deployed queue/deletion
recovery are incomplete. The local API tests use an isolated SQLite database;
a running MinIO/Postgres/Redis stack is still required to verify the full
direct-upload, private-artifact, deletion-worker, scheduler, comparison-worker,
and export-bundle runtime. Do not put real participant data into this
environment or use real provider keys before the required privacy, safety,
accessibility, and lived-experience review.
