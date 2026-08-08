# Phase 1 local development

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

Open `http://localhost:3000`, choose the local development account, and create an empty project. The browser receives only a short-lived backend token; it never receives the signing key.

## Checks

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
pnpm lint
pnpm typecheck
pnpm build
uv run --project services/api pytest
```

## Phase 1 limitations

No media upload, capture, AI, CAD, template execution, or physical output exists yet. MinIO proves the future storage boundary but is not used by this empty-project slice. Do not put real participant data into this environment.
