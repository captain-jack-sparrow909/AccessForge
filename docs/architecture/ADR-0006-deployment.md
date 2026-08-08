# ADR-0006: Vercel frontend and Render backend deployment

Status: proposed  
Date: 2026-08-08

## Context

The requested deployment split is Next.js on Vercel and backend/worker infrastructure on Render. AccessForge needs previews, long-running jobs, PostgreSQL, a Redis-compatible queue, and persistent object storage.

## Decision

- Deploy `apps/web` to Vercel using the Next.js App Router.
- Deploy the FastAPI API as a Docker-based Render web service.
- Deploy the Celery worker as a separate Docker-based Render background worker.
- Use Render PostgreSQL for domain state and Render Key Value for the queue/cache.
- Use an external S3-compatible object store for media/artifacts.
- Define backend services and datastores in `render.yaml`.
- Maintain separate local, preview/staging, and production environments.

Do not run heavy AI, computer vision, mesh, or CAD tasks inside Vercel functions. The browser polls durable job state through the API in the MVP.

## Alternatives considered

- Deploy everything on Vercel: unsuitable for long-running CAD/media workers and persistent backend state.
- Deploy everything on Render: possible, but conflicts with the requested frontend platform and gives up Vercel’s frontend preview workflow.
- Kubernetes: excessive operational burden for Phase 0/1.
- Serverless CAD functions: poor fit for native dependencies, resource limits, and reproducibility.

## Consequences

Positive:

- clear frontend/backend scaling boundary
- Render supports web, worker, Postgres, and Key Value primitives
- Vercel previews support frontend review without production data
- Docker provides reproducible CAD/runtime dependencies

Costs:

- cross-origin auth/CORS/token configuration
- multiple deployment environments and secret stores
- network latency between frontend and backend
- paid/staging resources may be needed for realistic CAD/media tests

## Deployment controls

- Preview deployments never use production data or production provider keys.
- Secrets are configured in platform secret settings, never committed or placed in Docker build arguments.
- Render readiness checks dependencies without making paid model calls.
- Database migrations are reviewed and run through controlled pre-deploy behavior.
- Worker shutdown allows safe completion/checkpointing and retry.
- Persistent data never depends on the Render service filesystem.

