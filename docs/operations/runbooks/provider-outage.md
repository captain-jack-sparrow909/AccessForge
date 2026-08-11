# Runbook: model-provider outage

## Status and boundary

**Unexercised.** This guide covers an unavailable, rate-limited, malformed, or
credential-rejected optional model-provider call. It applies only to approved
synthetic-data exercises. AccessForge must not automatically retry indefinitely,
switch vendors, send additional data categories, or use a fallback provider
without a new user choice and the required consent.

## Stop and contain

1. Stop initiating new external-provider requests in the affected environment.
2. Do not copy prompts, provider responses, API keys, object URLs, or project
   content into tickets, logs, or public channels.
3. Leave deterministic project, risk, CAD, and export gates unchanged. A model
   outage must not cause a risk downgrade or an export-policy change.
4. If a credential compromise is suspected, stop using that configuration and
   follow the incident/security response runbook.

## Inspect and recover

1. Record only safe metadata: timestamp, environment, provider type/model,
   sanitized error category, correlation or agent-run ID, and whether the
   request contained approved synthetic data.
2. Confirm the failed run is terminal and that no draft requirement revision
   was accepted from an incomplete or malformed provider response.
3. Verify that the user can continue through the non-AI/manual path or retry
   only after the provider is known to be available.
4. Run a single bounded synthetic probe or workflow retry after the approved
   recovery condition. Do not use a real participant project as a probe.
5. Stop again if the retry fails or returns a response that cannot pass the
   schema and citation checks.

## Record and escalate

Record the outage duration, safe error category, affected synthetic test IDs,
recovery result, and any user-visible impact. Escalate to the designated
technical owner. Escalate credential, data-exposure, or unsafe-output concerns
through the designated security/safety process; no contact is invented here.

## Completion criteria

The exercise is complete only when the approved synthetic retry and the manual
non-AI path behave as expected, with no secret or private content recorded.
Mark the drill evidence separately; this document alone is not drill evidence.
