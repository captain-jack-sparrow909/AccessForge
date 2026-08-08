# AccessForge

AccessForge is an open-source co-design tool for turning an access difficulty with a physical object into a personalized, parametric assistive-adapter candidate.

The repository is currently in **Phase 0: co-design, scope, safety, and architecture**. There is intentionally no application code yet. This phase makes the product boundaries and participant protections reviewable before implementation begins.

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
- [Project progress](PROGRESS.md)

## Status

Pre-alpha. Phase 0 documents are awaiting human review by the project owner and, before research starts, qualified accessibility, safety, privacy, and lived-experience contributors.

Phase 1 foundation work is now in progress. It provides an authenticated empty-project slice, local Postgres/Redis/MinIO services, FastAPI health endpoints, generated API-contract plumbing, and Vercel/Render deployment configuration. Capture, AI, CAD, and physical-output workflows do not exist yet.

## Local Phase 1 setup

See [the local development guide](docs/operations/local-development.md). The shortest path is:

```bash
pnpm install
uv sync --project services/api
pnpm dev:keys
pnpm generate:api
docker compose up --build api worker
```

Then run `pnpm dev` in another terminal and open `http://localhost:3000`.

## Contributions

Do not submit real user media, personal health data, or unreviewed physical-design templates. Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the safety documentation before opening an issue or pull request.
