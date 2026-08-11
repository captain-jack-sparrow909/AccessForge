# Operations runbooks

## Status

These are source-level response guides, not evidence of a completed operational
drill. Every drill in this directory is **unexercised** as of 2026-08-11.
They do not authorize a production test, a physical-output activity, a change
to safety policy, or the use of participant, health, or other private data.

## Preconditions for any exercise

- Obtain explicit approval from the project owner for the exact exercise.
- Use an isolated environment and approved synthetic data only.
- Assign an incident lead, technical operator, and escalation destination
  before starting. This repository does not define those contacts.
- Record a start time, environment, code revision, scope, expected failure,
  and stop condition in a restricted operational record. Do not use a public
  issue, commit message, or chat transcript for secrets or private data.
- Keep Phase 6 policy flags disabled and do not create a physical-use,
  manufacturing, safety, fit, or accessibility claim while exercising a
  system failure path.

## Common stop condition

Stop immediately if an exercise could affect a non-synthetic environment,
expose credentials or private object URLs, make data unavailable beyond the
approved scope, or create uncertainty about deletion, audit, or safety state.
Preserve only safe metadata, then escalate through the designated owner and
security/safety process.

## Runbooks

- [Model-provider outage](provider-outage.md)
- [Queue failure and worker recovery](queue-failure.md)
- [Deletion and recovery](deletion-recovery.md)
- [Backup and restore](backup-restore.md)
- [Incident and security response](incident-security-response.md)
