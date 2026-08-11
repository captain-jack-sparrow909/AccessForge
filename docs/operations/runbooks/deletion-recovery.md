# Runbook: deletion and recovery

## Status and boundary

**Unexercised.** A deletion request is not proof that all private data, object
versions, backups, derived artifacts, or provider-side copies are gone. Run
this guide only with an approved synthetic project in an isolated environment.
Never use it to test deletion of real participant, health, credential, or
production data.

## Stop and contain

1. Do not report deletion as complete while any durable deletion record,
   private-object cleanup, backup scope, or provider-retention question remains
   unresolved.
2. Do not bulk-delete a bucket, database, audit trail, or backup to make the
   current project look deleted.
3. Do not manually change a deletion job to succeeded, delete audit history, or
   suppress a failure record.
4. Stop and escalate if an exercise could touch a non-synthetic object key or
   if an object-store error may contain a URL, credential, or private data.

## Inspect and recover

1. Record the synthetic project ID, deletion-job ID, environment, object
   inventory count, start time, expected fault, and approved stop condition.
2. Verify that the project is unavailable for ordinary use while its deletion
   work remains visible only through an authorized, sanitized status path.
3. Simulate at most the approved dependency failure, such as a temporary
   private-object-store outage. Do not widen the test to another project.
4. Restore the dependency and use the supported durable recovery path. Verify
   that retries are bounded, idempotent, and auditable rather than silently
   treating a partial cleanup as success.
   A live direct-upload authorization must leave the job in
   `awaiting_upload_write_quiescence`; active CAD work must leave it in
   `awaiting_server_write_quiescence`. Neither state consumes the bounded
   failure retry budget.
   If the sanitized status is `object_storage_operation_timeout`, do not
   manually requeue it: automatic retries stop because the original SDK thread
   could still be in flight. Inspect the approved synthetic object inventory
   and follow the designated escalation path instead.
   If the status is `object_prefix_inventory_incomplete`, stop and verify the
   project-scoped list permission and pagination boundary. Never substitute a
   partial listing or known database keys for a complete prefix inventory.
5. Verify that orphan keys under the exact `private/<project-id>/` prefix are
   removed and that success follows two complete empty inventories separated by
   the configured settlement delay. Injecting one approved synthetic late key
   between passes should reset the confirmation sequence rather than succeed.
6. Verify the database/object inventory outcome against the declared scope.
   Keep any remaining backup, platform-retention, and provider-retention work
   explicitly recorded as incomplete.

## Record and escalate

Record only safe identifiers, counts, timestamps, status transitions, retry
outcomes, and reconciliation result. Escalate a failed or ambiguous cleanup to
the designated privacy/technical owner. Escalate suspected exposure, lost audit
history, or a hazardous output concern through the designated incident process.

## Completion criteria

Application-layer completion requires quiesced writers, a complete project
prefix reconciliation, and two separated empty confirmations. Exercise
completion still requires evidence for the approved synthetic scope and a
recorded statement of exclusions. It does not prove deletion from object
versions, backups, external providers, or any untested storage layer, and it
does not satisfy the Phase 7 exit gate by itself.
