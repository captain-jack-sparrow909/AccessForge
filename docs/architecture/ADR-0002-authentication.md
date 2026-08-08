# ADR-0002: Authentication and frontend-to-backend identity

Status: proposed  
Date: 2026-08-08

## Context

The frontend runs on Vercel and the API runs on Render. The browser needs authenticated project access without exposing OAuth provider tokens or backend secrets to the client. The product should remain replaceable across OIDC providers.

## Decision

Use Auth.js in Next.js with GitHub OAuth as the first login provider. Keep the browser session in secure HTTP-only cookies. The frontend issues a short-lived internal ES256 access token for calls to FastAPI.

The internal token contains `sub`, `iss`, `aud`, `exp`, `iat`, `jti`, `kid`, and role/membership claims. FastAPI verifies the signature, issuer, audience, expiry, and project authorization. The token expires within five minutes. Key rotation is represented by `kid` and a public-key set on the backend.

## Alternatives considered

- Clerk/Auth0: lower initial auth work, but introduces a hosted dependency and account cost into the open-source core.
- Supabase Auth: convenient, but couples identity to a second platform when the primary database is Render Postgres.
- Browser-to-API OAuth: increases CORS, callback, token-storage, and provider-token exposure complexity.
- Cookie sessions shared directly with FastAPI: cross-origin cookie and CSRF boundaries are harder to make explicit.

## Consequences

Positive:

- backend receives a stable internal identity contract
- OAuth provider can be replaced behind Auth.js
- short-lived tokens reduce impact of accidental exposure
- project authorization remains an API responsibility

Costs:

- key management and rotation are application responsibilities
- Vercel and Render must share public-key configuration correctly
- OAuth setup needs a preview/production callback policy

## Security requirements

- Never send GitHub access tokens to FastAPI or the browser’s application code.
- Use `HttpOnly`, `Secure`, and appropriate `SameSite` cookie settings.
- Validate exact allowed web origins and CORS.
- Protect cookie-authorized state changes against CSRF.
- Log token subject and request correlation ID, never token content.
- Provide account deletion, session revocation, and provider unlinking behavior.

