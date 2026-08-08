# AccessForge Progress

## Current phase

**Phase 0 — Co-design, scope, safety, and architecture**

Status: `in_progress`, Phase 1 authorized by the project owner; external safety/lived-experience review remains required before real data or physical outputs.

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

The project owner explicitly authorized beginning Phase 1 in the task conversation. This does not authorize collecting real participant data, connecting production credentials, or generating physical designs.

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
- `README.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `GOVERNANCE.md`

## Decisions and open questions

| ID | Decision or question | Status | Owner | Needed by |
| --- | --- | --- | --- | --- |
| D-001 | Initial MVP is limited to three passive grip/pull template families. | Decided in Phase 0 draft | Project owner + safety reviewers | Phase 1 |
| D-002 | AI produces structured proposals; deterministic CAD and risk code control generation/export. | Decided in Phase 0 draft | Technical maintainer | Phase 3 |
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

## Change log

### 2026-08-08

- Created the Phase 0 foundation documents.
- Marked all research and physical testing as planning only; no real participant data has been collected.
