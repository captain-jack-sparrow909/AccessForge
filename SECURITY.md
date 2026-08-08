# Security Policy

## Current status

AccessForge is pre-alpha and Phase 0 is documentation-only. It is not ready for real participant data, production API keys, or physical-device generation.

## Do not report publicly

Do not put any of the following in a public issue or pull request:

- provider API keys or OAuth secrets
- personal data, health-related information, or participant media
- private object-store URLs
- exploitable details that could expose another project
- instructions for bypassing AccessForge’s safety rules

## Reporting

Report security issues privately to `[security contact to be configured before Phase 1]`. Include a concise description, affected component/commit, reproduction steps using synthetic data, impact, and any suggested mitigation. Do not include secrets or real user data.

The maintainer will acknowledge receipt, assess severity, coordinate a fix, and publish a sanitized advisory when appropriate. Do not test against production or another user’s project without written authorization.

## High-priority areas

- broken object-level authorization
- private media or artifact exposure
- provider-key or signing-key leakage
- custom-endpoint SSRF
- arbitrary template/CAD code execution
- prompt injection that reaches privileged tools
- bypass of R2/R3 risk or export gates
- deletion claims that leave private data behind

## Safe-harbor expectations

Good-faith testing uses synthetic data, respects rate limits, avoids accessing other users’ information, and stops when a vulnerability is confirmed. The project will not pursue action for authorized, responsible reports that follow this policy.

Before Phase 1, replace the placeholder contact with a monitored security address and document response owners.

