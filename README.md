# AccessForge

AccessForge is an open-source co-design tool for turning an access difficulty with a physical object into a personalized, parametric assistive-adapter candidate.

The repository is currently in **Phase 6 source foundation: fail-closed
controlled-export records and hazard containment**. It builds on the consent-first project, capture and
measurement workflow, optional editable requirements assistant, and fixed CAD
templates. A private software candidate can only be queued through a current,
server-owned deterministic R1 decision with no unresolved assumptions. The
source can record an exact-revision acknowledgement, revalidate sealed risk
context, and contain a hazard report, but deployment policy and every current
template release keep controlled export disabled by default.

## MVP intention

The first public MVP will support only passive, non-load-bearing, low-energy grip and pull aids at room temperature:

- zipper or pull-tab extenders
- pen, stylus, brush, or similar cylindrical grip thickeners
- cabinet or drawer handle sleeves

The system will use confirmed user inputs and reviewed parametric templates. AI may help organize requirements and suggest bounded parameters, but it will not directly create meshes, execute arbitrary code, downgrade risk, or declare an output safe.

## Important safety boundary

Do not upload real participant media, health information, or private project data to this repository or to an undeclared cloud service. Do not use AccessForge for medical devices, mobility equipment, body-weight-bearing parts, child-safety systems, electrical/gas controls, weapons, hot/chemical environments, or any component whose failure could cause injury.

## Documentation map

- [Master implementation prompt](master-prompt.md)
- [Product requirements](docs/product/PRD.md)
- [Co-design research plan](docs/research/co-design-protocol.md)
- [Participant consent outline](docs/research/participant-consent-outline.md)
- [Risk taxonomy](docs/safety/risk-taxonomy-v0.1.md)
- [Threat model and data flow](docs/privacy/threat-model-and-data-flow.md)
- [Accessibility acceptance checklist](docs/accessibility/acceptance-checklist.md)
- [Low-fidelity workflow](docs/product/low-fidelity-workflow.md)
- [Metrics and physical-test assumptions](docs/product/metrics-and-assumptions.md)
- [Architecture decision records](docs/architecture/)
- [CAD engine and isolation boundary](docs/architecture/ADR-0005-cad-engine.md)
- [Model-provider boundary decision](docs/architecture/ADR-0007-model-provider-boundary.md)
- [Risk and private comparison decision](docs/architecture/ADR-0008-phase5-risk-and-comparison.md)
- [Controlled-export and hazard-containment decision](docs/architecture/ADR-0009-phase6-controlled-export.md)
- [Project progress](PROGRESS.md)

## Status

Pre-alpha. Phase 0 documents are awaiting human review by the project owner and, before research starts, qualified accessibility, safety, privacy, and lived-experience contributors.

Phase 1 foundation and the Phase 2 input workflow are implemented. Phase 3 adds a bounded AI assistant that turns selected project text and measurements into an editable, provenance-bearing requirements draft and clarification plan. It supports DeepSeek, OpenAI-compatible endpoints, OpenAI, Anthropic, Google/Gemini, and an offline fake adapter for local development. Phase 4 adds a repository-only template registry, immutable DesignSpecs, a deterministic CadQuery compiler, synthetic golden fixtures, and private candidate-artifact plumbing. Phase 5 adds deterministic risk decisions, immutable lineage, bounded private comparison batches, validation limitations, cancellation, and durable queue recovery. Phase 6 adds source-level sealed-risk revalidation, acknowledgement and bundle records, fixed-layout ZIP verification, feedback/hazard containment, and a reviewer-only non-human evidence schema. None of these source foundations authorize physical use, and all current releases remain blocked from controlled export.

## Phase 3 AI boundary

- AI is optional and disabled until a user deliberately creates and selects a provider configuration. Core deterministic workflows work without a model key.
- An external provider call requires separate active `ai_provider_sharing` consent and uses only the user-selected minimum data categories.
- Phase 3 never sends raw source images, video, audio, object-store URLs, or other project media to a model provider.
- Deployment-managed credentials remain in backend secret settings. Personal BYOK credentials are encrypted at rest and are never returned to the browser or stored in browser persistence.
- Requirements are proposals, not decisions: users can see provenance, edit every inference, and confirm a new immutable revision. AI cannot create geometry, lower risk, approve a design, or declare an output safe.
- The `fake` provider is restricted to local development and test use. It is not a production fallback.

## Phase 4 CAD boundary

- Only the three repository-bundled releases in the static template registry can run. A `reviewed_repository_only` release is not a physical-use approval, safety certification, or cryptographic signing claim. Community templates and any user-supplied Python, module name, archive, path, or geometry text are not executable.
- The compiler accepts a strict immutable DesignSpec, uses a short-lived subprocess with a disposable workspace, resource/time limits where supported, a stripped environment, fixed artifact names, and Python-level socket safeguards. These are defence-in-depth controls, not a complete OS security boundary.
- Current Docker Compose and Render worker deployments do not yet enforce compiler no-egress at the kernel/container/platform layer. A verified no-egress sandbox remains an operational exit gate; do not claim full network isolation.
- The Phase 4 report and Phase 5 validation record limited geometry/software checks only. They do not establish material suitability, printability, fit, retention, strength, comfort, accessibility benefit, or physical safety. Phase 6 controlled physical validation remains required before candidate approval or export.
- Synthetic repository fixtures may compile in tests. Private software candidate generation remains server-gated by a current Phase 5 deterministic R1 decision and no unresolved assumptions; it is not permission to manufacture, export, or use a physical part.

## Phase 5 risk and comparison boundary

- The deterministic ruleset, not a model, controls R0–R3 risk tiering and private candidate authorization. AI/provider settings remain optional and cannot lower risk, select unreviewed templates, execute code, approve, or export.
- A user first reviews two or three bounded reviewed-template variants, then explicitly queues the complete private comparison. Each candidate records its requirements, risk decision, immutable DesignSpec, plan/batch lineage, validation result, and private artifacts.
- The comparison view exposes tradeoffs, job outcome, deterministic validation state, and known or unassessed properties. A selection is recorded for software review only.
- The database is the durable queue record. Duplicate delivery, broker-publish uncertainty, cancellation, and stale worker claims have source-level recovery paths. Production queue, worker, PostgreSQL, storage, isolation, and accessibility exit gates remain open.

## Phase 6 controlled-export boundary

- The controlled-export page is intentionally default-denied. An acknowledgement is bound to one exact immutable candidate and is not professional approval, a safety certification, a fit result, manufacturing authorization, or permission for human physical use.
- Before a private ZIP could be recorded, the server requires fresh deterministic risk revalidation from an AES-GCM-sealed context, exact plan/batch/candidate/validation/artifact lineage, reviewer release controls, and non-human dimensional-fixture plus physical-coupon records. Current templates and deployment settings do not satisfy those conditions.
- Every future ZIP delivery repeats the current server gate and streams only through an authenticated no-store API response; AccessForge does not hand browsers a reusable object-store bearer URL. A later invalidation blocks future delivery requests, though it cannot retract bytes already received.
- Feedback is a private observation. A potential hazard creates a local block and invalidates current acknowledgement/bundle delivery; only a configured reviewer control can quarantine a template release globally.

## Local setup

See [the local development guide](docs/operations/local-development.md). The shortest path is:

```bash
pnpm install
uv sync --project services/api
pnpm dev:keys
pnpm generate:api
docker compose up --build api worker
```

Then run `pnpm dev` in another terminal and open `http://localhost:3000`. Use synthetic content only; do not upload real participant media.

Provider setup is optional. Keep `DEFAULT_MODEL_PROVIDER=none` to leave AI disabled. If you test a local BYOK configuration, set a backend-only, base64-encoded 32-byte `MODEL_CREDENTIAL_ENCRYPTION_KEY` in the repository-root `.env` for Compose (or in `services/api/.env` when starting the API from that directory); do not place a provider key or encryption key in an `NEXT_PUBLIC_*` variable. See [local development](docs/operations/local-development.md) and [ADR-0007](docs/architecture/ADR-0007-model-provider-boundary.md) for the full boundary.

## Contributions

Do not submit real user media, personal health data, or unreviewed physical-design templates. Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the safety documentation before opening an issue or pull request.
