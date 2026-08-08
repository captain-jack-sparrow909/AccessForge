# ADR-0004: S3-compatible object storage for media and artifacts

Status: proposed  
Date: 2026-08-08

## Context

AccessForge handles private source media and generated artifacts. Render service filesystems are ephemeral, and storing media in PostgreSQL would increase cost, backup scope, and exposure. The frontend needs large uploads without routing bytes through Vercel functions.

## Decision

Use an S3-compatible object-store interface with direct, short-lived presigned uploads/downloads. Local development uses MinIO. The hosted deployment may use an S3-compatible provider such as S3 or R2, selected after cost, privacy, region, and retention review.

PostgreSQL stores object metadata, ownership, checksum, content type, retention state, quarantine state, and deletion status—not the media bytes.

Use separate private and explicitly published namespaces/buckets. Every object key is unpredictable and includes a project-scoped prefix. Object access is authorized by FastAPI before presigning.

## Alternatives considered

- Render persistent disk: not ideal for portability, scaling, backup, or browser direct upload.
- PostgreSQL bytea: creates large database/backup burden and makes media lifecycle less clear.
- Vercel Blob: convenient frontend integration, but couples the backend’s persistent private data to the frontend platform.
- Public CDN URLs: unacceptable for private participant media.

## Consequences

Positive:

- direct browser upload/download
- portable storage adapter
- explicit retention and deletion jobs
- backend remains the authorization gate

Costs:

- object-store credentials and lifecycle policies must be configured correctly
- presigned URLs are capabilities and need short expiry/operation scope
- orphan cleanup and deletion verification are required

## Required controls

- private by default
- magic-byte and size validation after upload
- checksums and content-length constraints
- no sensitive object URLs in logs or analytics
- object-store encryption and restricted service credentials
- deletion/reconciliation job with auditable outcomes

