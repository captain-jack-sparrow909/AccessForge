# ADR-0002: Authentication and frontend-to-backend identity

Status: accepted
Date: 2026-08-08

## Context

The frontend runs on Vercel and the API runs on Render. The browser needs authenticated project access without exposing OAuth provider tokens or backend secrets to the client. The product should remain replaceable across OIDC providers.

## Decision

Use Better Auth in Next.js with first-party email/password accounts and optional
GitHub OAuth. Store Better Auth's user, credential/account, verification, and
session records in the existing PostgreSQL deployment under dedicated
`auth_*` tables. Keep the browser session in secure HTTP-only cookies. The
frontend issues a short-lived internal ES256 access token for calls to FastAPI.

The API service remains the sole schema-migration owner: Alembic creates and
updates the Better Auth tables. Vercel connects with a restricted PostgreSQL
URL but does not run schema mutation during builds or deploys. Better Auth user
IDs become the stable internal token subject regardless of whether the account
uses a password or GitHub.

The internal token contains `sub`, `iss`, `aud`, `exp`, `iat`, `jti`, `kid`, and role/membership claims. FastAPI verifies the signature, issuer, audience, expiry, and project authorization. The token expires within five minutes. Key rotation is represented by `kid` and a public-key set on the backend.

## Alternatives considered

- Clerk/Auth0: lower initial auth work, but introduces a hosted dependency and account cost into the open-source core.
- Supabase Auth: convenient, but couples identity to a second platform when the primary database is Render Postgres.
- Browser-to-API OAuth: increases CORS, callback, token-storage, and provider-token exposure complexity.
- Cookie sessions shared directly with FastAPI: cross-origin cookie and CSRF boundaries are harder to make explicit.

## Consequences

Positive:

- backend receives a stable internal identity contract
- sign-in does not require a GitHub account
- OAuth providers remain replaceable behind Better Auth
- short-lived tokens reduce impact of accidental exposure
- project authorization remains an API responsibility

Costs:

- key management and rotation are application responsibilities
- Vercel and Render must share public-key configuration correctly
- password recovery and verified-email delivery require a transactional email integration
- existing pre-migration Auth.js subjects need an explicit account-mapping plan before importing production data
- OAuth setup needs a preview/production callback policy

## Security requirements

- Never send password hashes or GitHub access tokens to FastAPI or the browser’s application code.
- Use Better Auth's password hashing implementation; never store plaintext credentials.
- Keep `BETTER_AUTH_SECRET` and `BETTER_AUTH_DATABASE_URL` server-only.
- Use `HttpOnly`, `Secure`, and appropriate `SameSite` cookie settings.
- Validate exact allowed web origins and CORS.
- Protect cookie-authorized state changes against CSRF.
- Log token subject and request correlation ID, never token content.
- Provide account deletion, session revocation, and provider unlinking behavior.
