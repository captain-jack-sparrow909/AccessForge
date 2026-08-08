# AccessForge Progress

## Current phase

**Phase 3 — Provider-neutral AI requirements assistance**

Status: `implementation_complete_pending_exit_gate`, Phase 3 is authorized by the project owner. The implementation and automated verification are complete; keyboard/screen-reader review and the required human safety, privacy, accessibility, and lived-experience review remain before real participant data, production provider credentials, or physical outputs. Phase 1 Docker/browser runtime checks remain environment-limited.

## Phase 0 checklist

- [x] Create a concise product requirements document and supported user journeys.
- [x] Define the three supported MVP template families.
- [x] Define prohibited and professional-review-required use cases.
- [x] Create a co-design research plan for 8–12 disabled participants and at least two relevant professionals.
- [x] Create a participant consent outline and compensation plan.
- [x] Create the versioned initial risk taxonomy and rules.
- [x] Create a threat model and privacy/data-flow inventory.
- [x] Create an accessibility acceptance checklist.
- [x] Create architecture decision records for the required platform boundaries.
- [x] Create a low-fidelity workflow and content model.
- [x] Define product, safety, accessibility, privacy, and reliability metrics.
- [x] List assumptions requiring controlled physical testing.
- [x] Add minimal community, governance, and security policies.
- [ ] Human review by the project owner.
- [ ] Review by lived-experience contributors and qualified professionals.
- [ ] Approve Phase 0 exit gate.

The project owner explicitly authorized beginning Phase 1 and continuing through Phase 3 in the task conversation. This does not authorize collecting real participant data, connecting production credentials, or generating physical designs.

## Phase 1 checklist

- [x] Create the monorepo package structure and development commands.
- [x] Add Next.js App Router web shell and accessible Phase 1 pages.
- [x] Add FastAPI service with liveness/readiness endpoints.
- [x] Add PostgreSQL models/migration for users and private projects.
- [x] Add project authorization skeleton and RFC 9457-style problem responses.
- [x] Add Auth.js/GitHub boundary and development-only local credentials.
- [x] Add short-lived ES256 frontend-to-backend token route and API verification.
- [x] Add local Docker Compose services for Postgres, Redis, MinIO, API, and worker.
- [x] Add Render Blueprint and Vercel environment documentation.
- [x] Add OpenAPI export and TypeScript API-client generation plumbing.
- [x] Add CI definitions and backend/frontend checks.
- [x] Install dependencies and run the Phase 1 source checks successfully.
- [x] Verify an API-level signed-token authenticated create/list/retrieve flow with project ownership.
- [ ] Verify the Docker API/worker image build and local Compose runtime (Docker daemon unavailable in this environment).
- [ ] Complete Phase 1 exit gate.

## Phase 2 checklist

- [x] Add deterministic project scope pre-screening with supported, blocked, and unknown outcomes.
- [x] Add persisted project state transitions and audit events with explicit allowed transitions.
- [x] Add participant records and immutable, separately revocable consent records.
- [x] Add text-only observation and explicit skip paths.
- [x] Add manual measurements with unit conversion, tolerance, method, unknown, and confirmation fields.
- [x] Add accessible capture UI with text, still-image, video, helper, and printable-marker alternatives.
- [x] Add S3-compatible direct-upload presigning with ownership and consent checks.
- [x] Add upload completion validation and quarantine state for expired or mismatched objects.
- [x] Add project deletion endpoint, auditable deletion jobs, and expired-upload retention task skeleton.
- [x] Add project workflow pages for new project, consent, capture, observation, measurements, and overview.
- [x] Add Phase 2 OpenAPI routes and TypeScript client methods.
- [x] Add backend coverage for the text/manual-measurement/deletion workflow.
- [ ] Verify full Postgres/Redis/MinIO runtime, direct object upload, and worker deletion locally.
- [ ] Complete Phase 2 exit gate with keyboard and screen-reader review.

## Phase 3 checklist

- [x] Add a vendor-neutral provider contract and adapters for DeepSeek, OpenAI-compatible, OpenAI, Anthropic, and Google/Gemini APIs.
- [x] Add a deterministic, offline fake provider for local development and provider-contract tests only.
- [x] Add capability probing and persist only conservative, timestamped capability metadata.
- [x] Add deployment-managed-key and AES-256-GCM BYOK configuration paths with non-sensitive fingerprints and revocation.
- [x] Add custom OpenAI-compatible endpoint validation with hosted SSRF controls and explicit self-hosted escape hatch.
- [x] Add model-provider settings, capability-test, selection, and revoke flows.
- [x] Add versioned prompt registry, schema contracts, and golden fixtures for ambiguity, missing measurements, and prompt injection.
- [x] Add bounded requirements extraction and clarification planning over selected text/measurements only.
- [x] Add provenance-bearing, immutable draft and user-confirmed requirement revisions.
- [x] Add sanitized agent-run/step metadata for provider/model, hashes, token counts, optional operator-priced cost estimates, latency, status, and error categories without private reasoning traces.
- [x] Require explicit `ai_provider_sharing` consent for an external provider request; do not send raw project media in Phase 3.
- [x] Keep AI outside geometry, risk lowering, approval, export, and deterministic workflow decisions.
- [x] Run the shared provider contract suite and Phase 3 API flow against the offline fake provider in the final verification pass.
- [ ] Run a deliberately configured external-provider smoke test only with synthetic data and an approved non-production key.
- [ ] Verify the model settings and requirements pages with keyboard and screen-reader review.
- [ ] Complete the Phase 3 exit gate.

## Phase 2 verification evidence

Passed:

- `uv run --project services/api ruff check services/api`
- `uv run --project services/api mypy services/api/accessforge`
- `DATABASE_URL=sqlite+aiosqlite:///./phase2test.db AUTO_CREATE_DB=true uv run --project services/api pytest` — 4 tests passed
- `pnpm generate:api`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm build`
- `uv run --project services/api alembic upgrade head` against a fresh local SQLite file

The API test covers project creation, scope evaluation, consent recording, text observation, inch-to-millimetre conversion, and queued deletion with owner authorization. The browser pages and storage-worker runtime still need a local service run for end-to-end verification.

## Phase 2 implementation notes

- Consent wording remains a product/legal draft; it is not approved research consent.
- Upload completion verifies declared size, content type, object existence, and expiry, but does not claim malware scanning or content redaction. Local Compose wires the API/worker to MinIO and the API creates the private bucket on first presign.
- The printable marker is a basic synthetic scale aid. Guided computer-vision measurement is not implemented.
- Deletion marks the project deleted immediately and queues media removal; the Celery worker must be running to complete object deletion.
- No AI provider receives project content in this phase.

## Phase 3 implementation notes

- AI is opt-in per project. A managed deployment key does not bypass a project's separate `ai_provider_sharing` consent; revocation prevents future external-provider calls.
- The Phase 3 provider boundary accepts text messages only. Selected project text and measurements may be supplied; raw source images, video, audio, object-store URLs, and other media bytes are excluded regardless of capture consent.
- Provider responses are schema validated and citation checked before a requirements revision is written. A user can inspect, correct, and confirm the result; an AI proposal never becomes a confirmed fact by itself.
- BYOK plaintext exists only while the backend encrypts it or performs an authorized provider call. It is not sent to Vercel/browser code, persisted in browser storage, included in telemetry, or returned by the API.
- `fake` / `development_fake` is an offline local-development and test facility. It is not allowed in production and is not an automatic fallback after a real provider failure.
- Deterministic Phase 1/2 behavior continues without a model key. Phase 3 does not generate geometry, call CAD, lower risk, approve a candidate, or make a safety claim.
- No external provider has been authorized for use with real participant data. Any future real-provider smoke test must use synthetic data, an approved non-production key, and a separately recorded result.

## Phase 3 verification status

Passed on a fresh temporary SQLite database:

- backend `ruff`, strict `mypy`, and `pytest` — 38 tests, including provider endpoint/model routing, all built-in provider adapters, offline fake extraction/confirmation, prompt-injection/citation rejection, schema rejection, and no-media context coverage
- AES-256-GCM credential and custom-endpoint safety tests
- a fresh Alembic upgrade through `0003_phase3_ai_requirements`
- generated OpenAPI/client, frontend lint/typecheck, and production web build
- Docker Compose configuration validation

No real provider call, production credential, participant data, or media was
used. External-provider smoke testing remains deliberately out of routine CI
and requires synthetic input plus separately approved non-production credentials.

## Phase 1 verification evidence

Passed:

- `pnpm install --frozen-lockfile`
- `pnpm generate:api`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm build`
- `pnpm format:check`
- `uv run --project services/api ruff check services/api`
- `uv run --project services/api mypy services/api/accessforge`
- `uv run --project services/api pytest` — 3 tests passed
- `docker compose config --quiet`
- signed-token smoke: authenticated project create/list/retrieve and owner scoping

Pending or environment-limited:

- Docker image build/start: Docker CLI is installed, but the local Docker daemon is not running.
- Browser-level OAuth/local-credential flow: the Auth.js boundary and local provider are implemented; run after starting the web/API services with `pnpm dev:keys` and Docker.

No production credentials, real participant data, or physical-design workflows were used.

## Evidence created in this phase

- `docs/product/PRD.md`
- `docs/research/co-design-protocol.md`
- `docs/research/participant-consent-outline.md`
- `docs/safety/risk-taxonomy-v0.1.md`
- `docs/privacy/threat-model-and-data-flow.md`
- `docs/accessibility/acceptance-checklist.md`
- `docs/product/low-fidelity-workflow.md`
- `docs/product/metrics-and-assumptions.md`
- `docs/architecture/ADR-0001-monorepo.md`
- `docs/architecture/ADR-0002-authentication.md`
- `docs/architecture/ADR-0003-async-jobs.md`
- `docs/architecture/ADR-0004-object-storage.md`
- `docs/architecture/ADR-0005-cad-engine.md`
- `docs/architecture/ADR-0006-deployment.md`
- `docs/architecture/ADR-0007-model-provider-boundary.md`
- `README.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `GOVERNANCE.md`

## Decisions and open questions

| ID | Decision or question | Status | Owner | Needed by |
| --- | --- | --- | --- | --- |
| D-001 | Initial MVP is limited to three passive grip/pull template families. | Decided in Phase 0 draft | Project owner + safety reviewers | Phase 1 |
| D-002 | AI produces structured proposals; deterministic CAD and risk code control generation/export. | Implemented as a Phase 3 boundary; pending external review | Technical maintainer | Phase 3 exit |
| D-003 | Select the final open-source and hardware-template licenses. | Open | Project owner + legal review | Before external contributions |
| D-004 | Select the first identity provider and GitHub OAuth application owner. | Proposed Auth.js + GitHub; open for review | Technical maintainer | Phase 1 |
| D-005 | Approve research consent wording and data-retention period. | Open | Project owner + privacy reviewer | Before recruitment |
| D-006 | Validate that all three template families are genuinely low-risk in the intended contexts. | Open physical assumption | Safety advisory group | Phase 6 |

## Phase 0 exit gate

Phase 0 is complete only when:

1. Supported and prohibited categories are unambiguous.
2. No critical architecture decision depends on an unstated assumption.
3. Safety, privacy, accessibility, and lived-experience reviewers can understand the data flow and challenge it.
4. The project owner explicitly approves moving to Phase 1.

## Phase 3 exit gate

Phase 3 is complete only when:

1. Every supported adapter passes the shared offline contract suite and the fake-provider requirements flow proves the no-media, schema, citation, provenance, and user-confirmation boundaries.
2. Malformed or unsupported provider output cannot enter domain requirement tables, and a user can see and correct every AI inference before confirmation.
3. BYOK encryption, revocation, and hosted custom-endpoint controls have source-level and integration coverage.
4. The model settings and requirements pages have keyboard and screen-reader review.
5. No real participant data, raw media, or production provider key has been used for implementation verification.

## Change log

### 2026-08-08

- Created the Phase 0 foundation documents.
- Marked all research and physical testing as planning only; no real participant data has been collected.
- Implemented the Phase 2 consent-first project workflow, manual measurements, capture/upload boundaries, and deletion foundations.
- Completed the Phase 3 optional, provider-neutral requirements-assistance boundary with explicit consent, no raw-media transfer, encrypted BYOK, offline fake-provider controls, immutable user-confirmed requirements, and provider telemetry.
