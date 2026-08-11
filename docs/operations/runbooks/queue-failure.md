# Runbook: queue failure and worker recovery

## Status and boundary

**Unexercised.** This guide covers broker unavailability, failed publication,
duplicate delivery, worker loss, and stale worker claims for private CAD work.
Use an isolated stack and approved synthetic fixtures only. Do not manually
alter candidate, job, risk, approval, or export state in a database to make an
exercise appear successful.

## Stop and contain

1. Stop creating additional generation work in the affected environment if
   backlog growth or duplicate dispatch is not part of the approved exercise.
2. Do not delete queued job rows, clear broker data, or bypass the server-side
   generation/risk gates to force completion.
3. Preserve the durable database records and safe timing/status metadata.
4. If non-synthetic data, credentials, or an unexpected object-store write is
   involved, stop and escalate before attempting recovery.

## Inspect and recover

1. Record the code revision, environment, synthetic candidate/job IDs, broker
   failure mode, worker state, and start time.
2. Verify that a failed publish leaves the durable job queued rather than
   creating an untracked or duplicate candidate.
3. Restore only the approved queue/worker dependency, then allow the supported
   recovery path to re-dispatch queued IDs and resolve stale claims.
4. Verify that at-least-once delivery creates at most one terminal candidate
   outcome and one coherent job outcome for the immutable candidate inputs.
5. Verify that cancellation and stale-lease behavior does not persist a partial
   private artifact bundle or open an approval/export path.

## Record and escalate

Record queue wait, recovery timing, duplicate-delivery outcome, stale-lease
outcome, safe failure categories, and any required cleanup result. Escalate a
recovery failure, lost audit trail, unexpected artifact, or safety-gate change
to the designated technical and safety owners.

## Completion criteria

The drill is complete only after the approved synthetic scenario has a durable,
auditable terminal state and any required private-object cleanup is verified.
Do not treat this guide or a unit test as evidence of deployed broker,
PostgreSQL, worker-acknowledgement, or object-storage behavior.
