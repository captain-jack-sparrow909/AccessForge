# ADR-0001: Monorepo and package boundaries

Status: proposed  
Date: 2026-08-08

## Context

AccessForge has a Next.js frontend, a Python API/worker, shared schemas, CAD templates, documentation, and deployment definitions. The repository is currently empty. The project needs frontend/backend changes to be reviewable together while keeping language-specific tooling clear.

## Decision

Use a single monorepo with:

- `apps/web` for Next.js
- `services/api` for FastAPI, worker, AI adapters, risk engine, CAD compiler, and tests
- `packages/api-client`, `packages/schemas`, and `packages/design-system` for generated or intentionally shared TypeScript assets
- `templates` for reviewed template manifests, fixtures, and documentation
- `docs` for ADRs, safety, research, privacy, accessibility, and operations

Use `pnpm` for JavaScript workspace management and `uv` for Python dependency management. Generate the TypeScript API client from FastAPI’s OpenAPI contract; do not duplicate request/response types manually.

## Alternatives considered

- Separate repositories: stronger service isolation, but slower cross-boundary reviews and harder reproducibility for an early-stage project.
- Full-stack TypeScript: simpler language count, but less suitable for the Python CAD, geometry, and computer-vision ecosystem selected for AccessForge.
- Python-only frontend: weaker fit for the Next.js/Vercel requirement and browser/3D ecosystem.

## Consequences

Positive:

- one pull request can update API schema, client, worker, template, docs, and tests
- one versioned source of truth for release and safety policy
- easier local synthetic end-to-end environment

Costs:

- CI must isolate changed packages and still run cross-boundary checks
- contributors need both Node and Python setup
- release/version policy must distinguish app, service, schema, and template changes

## Guardrails

- Keep Python and TypeScript domain logic separate; share schemas through generated artifacts.
- Do not import backend implementation into frontend packages.
- Require migration, API, template, safety, and accessibility review labels when applicable.
- Document exact tool versions and reproducible setup.

