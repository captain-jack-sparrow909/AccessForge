# Runbook: backup and restore

## Status and boundary

**Unexercised.** No backup/restore configuration or drill is approved by this
repository alone. A real exercise requires a platform owner, an approved
isolated restoration environment, documented retention/encryption controls,
and approved synthetic data only.

## Stop and contain

1. Do not restore into production, a shared development environment, or an
   environment with live provider credentials, public ingress, or non-synthetic
   data.
2. Do not copy master encryption keys, provider keys, session keys, private
   object URLs, or database dumps into tickets, local shells, source control,
   or public storage.
3. Keep Phase 6 controlled-validation and export flags disabled throughout the
   exercise. A restore must not recreate an authorization for physical output.
4. Stop if backup provenance, encryption-key availability, object-store scope,
   or restore target isolation cannot be demonstrated.

## Prepare and exercise

1. Define and record the backup scope separately for PostgreSQL, private object
   storage, encryption-key recovery, audit records, and deployment
   configuration. Do not assume one platform backup covers every component.
2. Define the recovery point/time objective, responsible owner, expected data
   exclusions, cleanup date for the restored synthetic environment, and stop
   condition before starting.
3. Restore only a known synthetic snapshot into a new isolated environment.
   Verify migrations, owner isolation, object inventory/checksums where
   applicable, and that no production endpoint or credential is reachable.
4. Validate only safe read paths and the approved synthetic workflow. Do not
   initiate a physical-output, provider, or broad data-deletion action merely
   to prove the restore.
5. Destroy the isolated exercise environment according to the approved plan
   and record any retained backup copies or platform-managed retention periods.

## Record and escalate

Record backup identifiers in the approved restricted system, the synthetic
dataset version, restoration environment, timings, integrity checks, gaps,
and cleanup evidence. Escalate missing keys, integrity mismatch, unexpected
private data, or inability to destroy the exercise environment to the
designated technical/privacy owner.

## Completion criteria

A backup/restore drill is complete only when its evidence shows an isolated
synthetic restore, declared integrity checks, declared exclusions, and cleanup.
This document does not establish that a production backup exists or that any
platform retention obligation has been met.
