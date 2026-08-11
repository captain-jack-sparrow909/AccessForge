# AccessForge Progress

## Current phase

**Phase 7 — Accessibility and reliability source foundation**

Status: `implementation_complete_pending_exit_gate`. The project owner
authorized the Phase 7 source foundation in the task conversation. It adds an
optional, on-demand 3D preview behind a structured report; source-level
accessibility contracts; a durable, sanitized deletion outbox with write
quiescence and project-prefix reconciliation; a separately configured Celery
scheduler; and unexercised incident
runbooks. It does not complete an accessibility audit, a compensated pilot, a
security review, a backup/restore exercise, or a deployed recovery drill. No
new setting approves a template, physical output, or physical-use claim.

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

The project owner explicitly authorized beginning Phase 1 and continuing through
the Phase 5 source foundation in the task conversation. This does not authorize
collecting real participant data, connecting production credentials, generating
a physical design, exporting an artifact, or making a physical-use claim.

## Phase 1 checklist

- [x] Create the monorepo package structure and development commands.
- [x] Add Next.js App Router web shell and accessible Phase 1 pages.
- [x] Add FastAPI service with liveness/readiness endpoints.
- [x] Add PostgreSQL models/migration for users and private projects.
- [x] Add project authorization skeleton and RFC 9457-style problem responses.
- [x] Add Better Auth email/password accounts with optional GitHub OAuth and persistent sessions.
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

## Phase 4 checklist

- [x] Add an immutable, provenance-bearing DesignSpec with canonical SI lengths and exact template-release references.
- [x] Add a static registry for the three repository-bundled template families and reject arbitrary paths, modules, archives, geometry text, and community code.
- [x] Add versioned manifests, synthetic fixtures, bounded parameter contracts, print/limitation documentation, and golden software tests.
- [x] Add deterministic CadQuery STEP/STL/GLB compilation, fixed artifact names, provenance, and hash metadata for synthetic fixtures.
- [x] Add private candidate/artifact persistence and an ID-only background-job boundary.
- [x] Add a short-lived compiler subprocess with a disposable workspace, stripped environment, Python socket safeguards, fixed outputs, wall-clock limit, and best-effort Unix resource limits.
- [x] Make the normal candidate route require a current Phase 5 R1 decision and no unresolved assumptions; Phase 4 creates pre-risk R0 DesignSpecs only.
- [x] Complete source, migration, API-client, frontend, and fresh-database verification for the Phase 4 implementation.
- [ ] Verify the Phase 4 Docker CAD image and Compose worker runtime (Docker daemon unavailable in this environment).
- [ ] Demonstrate a production-grade no-egress compiler sandbox at the kernel/container/platform layer; the current socket/subprocess controls are not sufficient evidence.
- [ ] Complete template-specific non-human fixture and controlled physical validation required by later phases.
- [ ] Complete the Phase 4 exit gate.

## Phase 5 checklist

- [x] Add a versioned deterministic R0–R3 risk engine with explainable findings, hashes, immutable assessment records, and R2/R3 fail-closed behavior independent of a model.
- [x] Add pre-generation and pre-export server gates that require current confirmed requirements, a current R1 decision, exact reviewed-template DesignSpec lineage, and no unresolved assumptions.
- [x] Invalidate stale risk decisions after risk-relevant project, observation, measurement, or requirements changes; block those edits while private generation is active.
- [x] Add bounded deterministic Template Matcher, Design Planner, and Design Critic roles with typed allowlisted tools, persisted checkpoints, and explicit model/tool ceilings.
- [x] Add server-validated two-or-three-variant plans, immutable plan proposals, and user-controlled waiting, single-selection, cancellation, and comparison paths.
- [x] Add durable private comparison batches with idempotent queue creation, candidate/job lineage, conditional cancellation, batch-only finalization, and post-comparison software-review selection.
- [x] Add normalized deterministic validation records and accessible comparison views that show tradeoffs, outcomes, and unassessed limitations.
- [x] Add durable queued-job dispatch recovery, stale-worker terminal recovery, and compare-and-set worker claim/finalization fencing.
- [x] Regenerate OpenAPI/client contract and verify source, migration, backend, and web checks.
- [ ] Exercise the broker, Celery acknowledgement/redelivery, PostgreSQL locking, S3 cleanup, and worker-loss recovery paths in a deployed or Docker runtime.
- [ ] Complete keyboard and screen-reader review of the risk and comparison workflow.
- [ ] Complete the Phase 5 exit gate.

## Phase 6 checklist

- [x] Add a separate AES-GCM-sealed risk-context record so export-time risk revalidation never trusts browser-resubmitted text; legacy/no-key rows fail closed.
- [x] Add immutable export validation, exact-revision acknowledgement, private bundle, feedback, hazard, reviewer release-control, and non-human evidence records with a migration.
- [x] Require complete current R1/requirements/spec/plan/batch/candidate/validation/artifact lineage and verify fixed names, byte lengths, and SHA-256 values before ZIP assembly.
- [x] Revalidate immediately before acknowledgement, bundle assembly, and every authenticated download; invalidate approvals and bundle delivery when relevant risk inputs, reviewer controls/evidence, or a local hazard changes.
- [x] Add a deterministic fixed-layout bundle, plaintext limitations/print guidance, manifest verification, authenticated no-store ZIP delivery (never a raw object-store bearer URL), and deletion-worker cleanup foundations.
- [x] Add typed private feedback and a local hazardous-result stop path; reserve global template quarantine for configured reviewer roles only.
- [x] Add a restricted versioned non-human dimensional-fixture/coupon schema and reviewer release-control API, all disabled by default.
- [x] Add a default-denied web workflow, generated OpenAPI/client contract, source-level utility tests, strict backend checks, migration round-trip, and webpack production build.
- [ ] Obtain independently reviewed template-release controls and qualified non-human evidence. Do not create synthetic records as a substitute.
- [ ] Exercise real storage, PostgreSQL locking, revocation/download races, deletion cleanup, reviewer authorization, and hazard containment in a deployed or Docker runtime using approved synthetic fixtures only.
- [ ] Complete accessibility, privacy, safety, qualified-review, and lived-experience review before enabling any Phase 6 deployment policy.
- [ ] Implement a trusted reviewer-role provisioning path. The current browser-to-API token intentionally carries `member`, so the `safety_reviewer` controls remain fail-closed.
- [ ] Complete the Phase 6 exit gate. No current template release is eligible for controlled export.

## Phase 7 checklist

- [x] Make the structured candidate report primary and load the private 3D preview only after an explicit user action.
- [x] Add source contracts for optional 3D, native upload controls, visible focus, reduced motion, forced colors, and wrapped navigation; run them in CI.
- [x] Define fail-closed Core Web Vitals, transfer, low-end-device, and slow-network performance budgets without inventing a measured pass.
- [x] Add a durable deletion outbox with opaque owner status, compare-and-set leases, bounded retry, stale-lease recovery, and conservative timeout/manual-review handling.
- [x] Prevent concurrent initial deletion requests from creating duplicate active outboxes or returning an integrity-error response.
- [x] Fence deletion against direct-upload and CAD/export write windows, reconcile the complete fixed private-project prefix, and require two separated empty confirmations before success.
- [x] Configure a dedicated Celery beat scheduler, clean-process task/schedule checks, one API migration owner, and read-only schema-head startup gates for independently deployed workers.
- [x] Add synthetic-only response runbooks for provider outage, queue failure, deletion/recovery, backup/restore, and incident/security response.
- [ ] Run browser/assistive-technology/keyboard/forced-colors/low-end-device checks and an authorized, compensated participant pilot.
- [ ] Exercise provider outage, queue failure, deletion/recovery, backup/restore, and incident paths in an approved isolated Docker or deployed environment.
- [ ] Complete independent security review and remediation.
- [ ] Complete the Phase 7 exit gate.

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

## Phase 4 implementation notes

- `reviewed_repository_only` means a release is bundled and resolved by the
  static registry. It is not a physical-use approval, safety certification, or
  cryptographic signature. No user/community template code is executable.
- The compiler receives only a validated DesignSpec JSON document, resolves a
  fixed generator, writes a fixed artifact set into a disposable workspace, and
  returns hashes and structured metadata. Its subprocess removes inherited
  secrets/proxy variables, sets resource limits where supported, bounds native
  library threads, and disables Python-level socket/DNS/connection creation.
- Those safeguards do not block native-code/raw-syscall networking and the
  current Compose/Render worker still has a normal container network. A
  verifiable no-egress sandbox remains an operational requirement before making
  a no-network claim or enabling real-user compilation.
- The Phase 4 report performs limited software/mesh checks and explicitly marks
  minimum wall thickness and print-orientation/overhang as not assessed. It
  does not demonstrate fit, retention, strength, durability, material behavior,
  comfort, printability, accessibility benefit, or physical safety.
- Synthetic fixture compilation is permitted in automated tests. Normal project
  DesignSpecs are R0 pre-risk records, so the user candidate route remains
  unavailable until Phase 5 creates a current R1 decision with no unresolved
  assumptions. Phase 6 remains required for approval/export and controlled
  physical validation.

## Phase 4 verification evidence

Passed:

- fresh Alembic upgrade through `0004_phase4_cad_candidates` against a
  disposable SQLite database;
- backend format, lint, and strict `mypy` checks;
- fresh-database backend suite — 64 tests passed, including deterministic
  STEP/STL/GLB/provenance hashes, manifest/range/cross-parameter rejection,
  static-template trust boundaries, private artifact persistence/cleanup, and
  the Phase 5 generation hard gate;
- generated OpenAPI/client, frontend formatting/lint/type checks, and the
  production Next.js build with the DesignSpec and private GLB viewer route.
- a disposable wheel build contained the reviewed manifests, synthetic
  fixtures, and template documentation required at runtime.

Environment-limited:

- `docker compose build api worker` could not run because this environment's
  Docker daemon is not running. No container image or Compose runtime claim is
  made from this session.

## Phase 5 implementation notes

- The deterministic risk engine is the sole source of R0–R3 decisions and
  generation permissions. The configured model-provider boundary is not called
  by this workflow and cannot lower risk, select a template, execute code,
  change immutable records, approve, export, manufacture, or authorize use.
- A successful R1 decision produces a risk-bound immutable DesignSpec. Plans,
  comparison batches, candidates, validation runs, and artifacts retain that
  lineage and fail closed when it becomes stale.
- The preferred path queues two or three reviewed-template variants only after
  a waiting-for-user checkpoint. A selection records a private candidate for
  software review only; it is not approval or a physical-use conclusion.
- The validation report distinguishes deterministic software findings from
  needs-confirmation and not-assessed limitations. It does not establish fit,
  strength, printability, material behavior, comfort, accessibility benefit, or
  physical safety.
- A committed queued `CadJob` is the durable dispatch record. The source-level
  periodic dispatcher safely re-publishes queued IDs; worker claims,
  cancellation, finalization, and stale-lease recovery use conditional durable
  state changes. This has not yet been exercised with deployed PostgreSQL,
  Redis/Celery, object storage, or process loss.

## Phase 5 verification evidence

Passed with synthetic fixtures and a fresh temporary SQLite database:

- `uv run --project services/api ruff check services/api`;
- `uv run --project . mypy accessforge` from `services/api` — strict typecheck
  passed for 73 source files;
- fresh-database backend suite — 91 tests passed, covering R2/R3 and
  prompt-injection corpus decisions, stale-input invalidation, immutable
  lineage, direct-plan-bypass rejection, private comparison lifecycle,
  cancellation, duplicate delivery, broker-publish recovery, stale leases, and
  validation limitations;
- fresh Alembic upgrade through `0005_phase5_risk_and_planning`, downgrade to
  `0004_phase4_cad_candidates`, and upgrade again;
- regenerated OpenAPI and TypeScript client, then `pnpm format:check`,
  `pnpm lint`, and `pnpm typecheck`;
- `pnpm --filter @accessforge/web exec next build --webpack` completed a
  production web build.

Environment-limited:

- The default Next.js Turbopack build cannot bind a sandbox port while processing
  CSS in this environment. The webpack production build above completed; no
  browser, deployed Vercel, or hosted API/worker runtime claim is made here.
- Docker is unavailable, so PostgreSQL/Redis/MinIO/Celery and deployment-grade
  compiler-isolation recovery remain open operational checks.

## Phase 7 implementation notes

- A 3D GLB preview is optional. The candidate's structured parameter,
  validation, and limitation report renders first and remains usable when the
  preview is never requested or cannot load. This is a source-level safeguard,
  not a claim of accessibility conformance.
- Phase 7 now has explicit Core Web Vitals, cold-transfer, low-end lab, and
  real-device budgets. No Lighthouse, field-data, or real-device result has
  been recorded, so the performance evidence gate remains open.
- Private cleanup is a durable database outbox. Worker leases and finalization
  use conditional state changes; failures expose only bounded opaque categories
  to an owner. A timeout stops automatic retry and requires manual review so a
  still-running SDK thread cannot overlap another automatic cleanup attempt.
- Project deletion and server-side private writers share a project-row barrier.
  Cleanup waits out previously issued direct-upload URLs, waits for active CAD
  jobs, deletes both known and orphaned project-prefix keys, and requires two
  separated complete empty inventories. Incomplete inventory evidence fails
  closed to manual review.
- The separate scheduler publishes deletion and CAD recovery work from a
  declarative Celery beat schedule. The API alone owns hosted migrations;
  worker/scheduler startup performs a read-only repository-head comparison.
  Source configuration and clean-process registration are covered, but no
  Docker, Redis, PostgreSQL, object-storage, deployment, backup, or incident
  exercise was run here.
- Runbooks are restricted to owner-approved, isolated, synthetic exercises.
  They deliberately do not invent contacts, outcomes, security findings, or
  participant evidence.

## Phase 7 verification evidence

Passed on synthetic/local source fixtures:

- `DATABASE_URL=<disposable-sqlite-url> AUTO_CREATE_DB=true uv run --project services/api pytest -q` — 125 passed, 1 PostgreSQL-only concurrency regression skipped.
- `uv run --project services/api pytest services/api/tests/test_phase7_deletion_recovery.py -q` — 17 passed, 1 PostgreSQL-only concurrency regression skipped.
- `uv run --project services/api ruff check services/api`
- `uv run --project services/api mypy --config-file services/api/pyproject.toml services/api/accessforge` — 80 source files checked.
- Fresh SQLite migration `0006 -> 0007 -> 0006 -> 0007` round-trip and `python -m accessforge.db.schema_gate` at head.
- `pnpm generate:api`, `pnpm lint`, `pnpm typecheck`, and `pnpm format:check`.
- `vitest run` — 3 Phase 7 accessibility source tests passed.
- `next build --webpack` — production web build completed with the deletion-status route.
- `docker compose config --quiet` and `git diff --check`.

The concurrent first-DELETE regression remains executable only against
PostgreSQL because SQLite does not implement `SELECT FOR UPDATE`; it returns a
database-lock error for that artificial two-writer interleave. No deployed
PostgreSQL, Redis, object-store, Render, Vercel, browser, assistive-technology,
participant, backup/restore, security, or incident exercise is claimed.

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
- Browser-level account flow: Better Auth email/password and optional GitHub OAuth are implemented; run the migration-backed end-to-end flow after starting the web/API services with `pnpm dev:keys` and Docker.

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
- `docs/architecture/ADR-0008-phase5-risk-and-comparison.md`
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
| D-004 | Select the first identity methods and GitHub OAuth application owner. | Better Auth email/password selected; GitHub remains optional and its application owner is open for review | Technical maintainer | Phase 1 |
| D-005 | Approve research consent wording and data-retention period. | Open | Project owner + privacy reviewer | Before recruitment |
| D-006 | Validate that all three template families are genuinely low-risk in the intended contexts. | Open physical assumption | Safety advisory group | Phase 6 |
| D-007 | Choose and verify a deployment-grade, no-egress compiler sandbox for the Render/container runtime. | Open operational security gate | Technical maintainer + security reviewer | Phase 4 exit |
| D-008 | Exercise the durable CAD dispatch/recovery model with PostgreSQL, Celery/Redis, storage, worker loss, and cancellation races. | Open operational security gate | Technical maintainer | Phase 5 exit |

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

## Phase 4 exit gate

Phase 4 is complete only when:

1. A fixed DesignSpec, exact bundled template release, seed, and supported build environment reproduce the documented geometry/hash evidence for every synthetic fixture.
2. Every template contract rejects missing, non-finite, out-of-range, and invalid-combination values before compilation.
3. The registry cannot execute untrusted template code, paths, modules, archives, or geometry text.
4. Candidate artifacts are private, immutable, and tied to their exact DesignSpec/template/provenance records.
5. The compiler's resource and no-egress isolation are demonstrated at the deployment layer, rather than inferred from the subprocess or Python socket controls.
6. No real-user candidate compilation, physical-output approval, or safety claim is enabled until Phase 5/6 gates are satisfied.

## Phase 5 exit gate

Phase 5 is complete only when:

1. Deterministic R2/R3 corpus cases are blocked without any model decision,
   and stale inputs invalidate the current R1 decision before generation.
2. Every private candidate traces to a confirmed requirements revision, current
   risk assessment, exact reviewed-template DesignSpec, plan/batch where
   applicable, validation record, and private artifact metadata.
3. The bounded planner cannot execute code, dynamically load an unreviewed
   template, lower risk, bypass validation, approve, export, manufacture, or
   authorize physical use.
4. The comparison is keyboard/screen-reader reviewed and clearly exposes each
   variant's tradeoffs, outcome, unknowns, and unassessed properties.
5. A deployed or Docker runtime demonstrates broker outage recovery, duplicate
   delivery fencing, cancellation/completion races, worker loss/stale-lease
   recovery, PostgreSQL finalization locking, and private object cleanup.
6. No Phase 5 output is presented as approved, exportable, fit, safe, or ready
   for physical use; Phase 6 retains those gates.

## Phase 7 exit gate

Phase 7 is complete only when:

1. No critical accessibility, privacy, security, or safety issue remains open
   for core tasks, based on dated evidence rather than source inspection alone.
2. Core workflows are independently shown to work without camera, audio,
   mouse, or a 3D-only interaction, including with relevant assistive
   technology and a compensated, authorized participant pilot.
3. Provider outage, queue failure, deletion/recovery, backup/restore, and
   incident procedures are exercised in an approved isolated environment and
   their outcomes/remediations are recorded without private data.
4. An independent security review is complete and all release-blocking findings
   are remediated or explicitly accepted by the authorized owner.

## Change log

### 2026-08-08

- Created the Phase 0 foundation documents.
- Marked all research and physical testing as planning only; no real participant data has been collected.
- Implemented the Phase 2 consent-first project workflow, manual measurements, capture/upload boundaries, and deletion foundations.
- Completed the Phase 3 optional, provider-neutral requirements-assistance boundary with explicit consent, no raw-media transfer, encrypted BYOK, offline fake-provider controls, immutable user-confirmed requirements, and provider telemetry.
- Began the Phase 4 deterministic CAD foundation: repository-only template contracts, immutable DesignSpecs, synthetic fixture compilation, private artifact plumbing, and subprocess/resource/socket safeguards. The production no-egress compiler sandbox and all real-user/physical-output gates remain open.

### 2026-08-09

- Implemented the Phase 5 deterministic risk, validation, bounded comparison,
  immutable-lineage, cancellation, and durable recovery source foundation.
- Verified the source implementation with a fresh SQLite migration round-trip,
  strict backend checks, 91 backend tests, regenerated API client, and a
  webpack production web build.
- Kept approval, export, manufacturing, physical use, deployed queue recovery,
  no-egress isolation, and human accessibility review as explicit open gates.
- Implemented the Phase 6 default-denied export and non-human-validation source
  foundation; no template release was enabled for export or physical use.
- Implemented the Phase 7 source foundation: optional 3D viewing, accessibility
  source contracts, durable deletion recovery, scheduler configuration, and
  synthetic-only response runbooks. Pilot, browser, security, backup/restore,
  and deployed recovery evidence remain open.

### 2026-08-11

- Hardened Phase 7 cleanup against outstanding direct-upload URLs and
  server-side private writes, added complete project-prefix orphan cleanup, and
  required two separated empty reconciliations before success.
- Made the API the single hosted migration owner and added read-only migration
  head gates for independently deployed worker and scheduler processes.
- Verified the source foundation with 125 backend tests, strict checks, a fresh
  migration round-trip, 3 web source tests, and a webpack production build.
  PostgreSQL/object-store recovery drills, accessibility/pilot evidence,
  backup/restore, and independent security review remain open.
- Defined low-end-device, slow-network, Core Web Vitals, and cold-transfer
  budgets as future release gates; no measurement result was fabricated.
