# AccessForge

AccessForge is an open-source co-design tool for turning an access difficulty with a physical object into a personalized, parametric assistive-adapter candidate.

The repository is currently in **Phase 3: provider-neutral AI requirements assistance**. It builds on the consent-first project, capture, and measurement workflow with an optional, editable requirements-extraction and clarification flow. CAD, physical-output, and professional-safety workflows remain deferred.

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
- [Model-provider boundary decision](docs/architecture/ADR-0007-model-provider-boundary.md)
- [Project progress](PROGRESS.md)

## Status

Pre-alpha. Phase 0 documents are awaiting human review by the project owner and, before research starts, qualified accessibility, safety, privacy, and lived-experience contributors.

Phase 1 foundation and the Phase 2 input workflow are implemented. Phase 3 adds a bounded AI assistant that turns selected project text and measurements into an editable, provenance-bearing requirements draft and clarification plan. It supports DeepSeek, OpenAI-compatible endpoints, OpenAI, Anthropic, Google/Gemini, and an offline fake adapter for local development.

## Phase 3 AI boundary

- AI is optional and disabled until a user deliberately creates and selects a provider configuration. Core deterministic workflows work without a model key.
- An external provider call requires separate active `ai_provider_sharing` consent and uses only the user-selected minimum data categories.
- Phase 3 never sends raw source images, video, audio, object-store URLs, or other project media to a model provider.
- Deployment-managed credentials remain in backend secret settings. Personal BYOK credentials are encrypted at rest and are never returned to the browser or stored in browser persistence.
- Requirements are proposals, not decisions: users can see provenance, edit every inference, and confirm a new immutable revision. AI cannot create geometry, lower risk, approve a design, or declare an output safe.
- The `fake` provider is restricted to local development and test use. It is not a production fallback.

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
