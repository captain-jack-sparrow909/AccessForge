# ADR-0003: Durable asynchronous jobs

Status: proposed  
Date: 2026-08-08

## Context

Media processing, model calls, CAD compilation, validation, and export may exceed a web request timeout. Vercel should remain a frontend surface; Render should run the API and long-lived workers. Results need durable state, retries, cancellation, and progress.

## Decision

Use FastAPI for request validation and job creation, PostgreSQL for durable job/project state, Celery for queued execution, and Render Key Value as the Redis-compatible broker/result transport. Run a separate Render background worker.

Every job has a durable state machine and checkpointed steps in PostgreSQL. Queue payloads contain IDs and configuration references, not raw media, decrypted provider keys, or large blobs. Workers read/write through authorized services and object storage.

## Alternatives considered

- Synchronous API requests: simple, but unsuitable for CAD/media and fragile under provider latency.
- Render Workflows: promising managed option, but the MVP needs a portable local stack and a mature Python worker path.
- Temporal: powerful durability and workflow history, but introduces another operational system before the domain state machine is understood.
- BullMQ: strong Node option, but separates the queue language from the Python CAD/worker service.

## Consequences

Positive:

- local Redis-compatible development path
- clear retry and failure categories
- independent API/worker scaling
- portable to another broker or durable workflow engine later

Costs:

- queue delivery is at-least-once; tasks must be idempotent
- Redis is not the source of truth
- cancellation is cooperative and must be tested
- worker shutdown and migration compatibility require operational discipline

## Guardrails

- Never retry deterministic schema/validation failures as transient provider failures.
- Store step results and artifact references before acknowledging jobs.
- Set bounded time, memory, output-size, and provider-cost limits.
- Use correlation IDs across API, queue, worker, model provider, CAD, and artifact records.

