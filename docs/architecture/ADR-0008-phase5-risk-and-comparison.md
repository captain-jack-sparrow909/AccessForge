# ADR-0008: Phase 5 deterministic risk, private comparison, and durable recovery

Status: proposed — Phase 5 foundation implemented; operational recovery exit gate open  
Date: 2026-08-09

## Context

Phase 5 connects confirmed requirements to two or three explainable, private
CAD candidates. That adds several boundaries which must remain independent:

- a deterministic decision about whether candidate generation is permitted;
- an immutable chain from confirmed requirements through the reviewed template
  and generated artifact; and
- asynchronous compilation that can be cancelled, redelivered, or interrupted
  without creating an unreviewed, duplicated, or misleading result.

A language model can help explain bounded alternatives in later iterations, but
it is not a safety authority, CAD executor, job authority, or approval system.
The phase also stops before export, manufacture, and physical-use claims.

## Decision

### Deterministic risk is the generation authority

Use a versioned, deterministic risk engine for the current project facts,
confirmed requirements, intended-use context, reviewed template release, and
visible unknowns. Each assessment records its ruleset version/hash, input and
decision hashes, tier, evidence references, unresolved questions, and allowed
actions.

Only a current R1 assessment that explicitly allows `generate_candidate` may
create private candidates. R0, R2, and R3 results fail closed. R2/R3 blocking
must not depend on a model response. A model or planner may raise a risk signal
or ask for review, but cannot lower a tier, add an allowed action, or suppress a
finding.

Risk-relevant project text, text observations, measurements, confirmed
requirements, reviewed-template identity, and risk context invalidate the
active assessment when changed. Risk-relevant edits are blocked while
generation is in progress. The worker rechecks the current deterministic gate
immediately before compilation and before artifact metadata is committed.

### Preserve immutable lineage and fail closed

The required lineage is:

```text
confirmed RequirementRevision
  -> immutable DesignSpecRevision
  -> immutable RiskAssessment and risk-bound DesignSpecRevision
  -> immutable DesignPlan and DesignPlanProposal variants
  -> CandidateGenerationBatch
  -> CandidateDesign + CadJob
  -> CandidateValidationRun + private immutable artifacts
```

Each generation check must verify the exact project, confirmed requirements
revision, current risk assessment, risk-bound DesignSpec, reviewed template
release, and—where relevant—the authorized plan and batch. A DesignSpec that
belongs to a plan cannot bypass its user checkpoint through the legacy
single-candidate route. Foreign keys, immutable hashes, and server-owned
identifiers are used for lineage; browser-provided tier, plan, template, or
approval assertions are never trusted.

### Compare a bounded private batch

The primary Phase 5 path creates a durable batch of two or three meaningful,
server-validated variants from one reviewed-template plan. The user must first
see a `waiting_for_user` checkpoint and explicitly request the complete private
comparison. That request is idempotent for the plan and creates the batch,
candidate rows, and durable jobs atomically before any broker submission.

The project remains `generating` until every child is terminal. Batch
reconciliation—not an individual child—sets the final plan/project state:

- at least one successful child: `candidates_ready` and a completed or
  completed-with-failures batch;
- every child cancelled: a cancelled batch and a return to
  `ready_for_generation`; and
- no successful child for another reason: a failed batch and a return to
  `ready_for_generation`.

Cancellation is cooperative. It must use conditional state transitions so a
stale cancellation request cannot overwrite a completed child or its artifact
metadata. The comparison view always shows variant identity, deterministic
validation state, failures, tradeoffs, and unknown or unassessed properties.
A post-comparison choice records a candidate for software review only; it is
not approval.

### Keep the agent contract bounded and inspectable

The Template Matcher, Design Planner, and Design Critic are a domain-owned,
typed state machine, not a general autonomous agent framework. The current
Phase 5 foundation uses deterministic reviewed-template planning; a future
model-assisted implementation must retain the same persisted prompt/version,
typed-tool, iteration-limit, and checkpoint contract.

The allowed tools are limited to reviewed-template search/contract lookup and
pausing for user confirmation. The workflow has explicit model-turn and tool
call ceilings. It may propose bounded parameter variants and explain tradeoffs,
but it may not execute code, dynamically import a template, retrieve unreviewed
template code, edit immutable records, lower risk, bypass validation, approve,
export, manufacture, or authorize physical use. Every proposed variant is
validated by server-owned schema and reviewed-template constraints before it is
persisted or queued.

### Make queue delivery recoverable

PostgreSQL is the durable source of truth; the broker is a delivery mechanism
with at-least-once semantics. Queue messages contain only durable IDs and no
raw project data, credentials, or artifact bytes.

The job implementation must satisfy all of the following before the operational
Phase 5 exit gate is claimed:

- write an outbox record or equivalent durable dispatch state in the same
  transaction as every `CadJob`;
- have a periodic/idempotent dispatcher recover queued work after an API crash
  between database commit and broker publish;
- acknowledge a worker task only after durable state is recorded, and reject or
  redeliver work lost with a worker process;
- claim candidate/job execution with compare-and-set transitions so duplicate
  deliveries cannot compile or persist a second artifact set;
- use a bounded, classified retry/recovery policy for transient infrastructure
  failures, while deterministic schema, risk, and validation failures become
  terminal without retry;
- lease or fence running attempts so a recovered attempt cannot be overwritten
  by an older worker that resumes late; and
- reconcile batch completion in a short transaction. PostgreSQL row locks may
  serialize finalization; SQLite support additionally requires guarded
  compare-and-set updates and bounded busy retries because `FOR UPDATE` is not
  a SQLite lock.

These requirements extend ADR-0003 rather than making Redis or Celery the
system of record.

### Preserve the Phase 5 boundary

Phase 5 artifacts are private and visible only through authorized project
access. Deterministic validation reports describe measured software checks,
failed checks, needs-confirmation findings, and not-assessed limitations. They
do not establish fit, strength, printability, material suitability, comfort,
accessibility benefit, safety, manufacturing suitability, or any physical-use
outcome.

There is no Phase 5 approval, export, manufacturing, or physical-use endpoint.
Any future export flow must re-evaluate the current risk, immutable lineage,
and validation state after an explicit Phase 6 approval and controlled physical
validation process.

## Alternatives considered

- **Model-controlled risk or generation authorization:** rejected because a
  probabilistic provider cannot be the only blocker for prohibited use.
- **Unbounded agent framework or generated CAD code:** rejected because it
  widens the tool, code-execution, and reproducibility boundary.
- **One preselected candidate instead of a comparison batch:** rejected because
  it hides meaningful parameter tradeoffs and bypasses the Phase 5 comparison
  requirement.
- **Broker-only job state or publish-after-commit without recovery:** rejected
  because crashes and at-least-once delivery would strand work or duplicate
  artifacts.
- **Calling a completed software result an approval:** rejected because no
  Phase 5 check establishes physical safety or suitability.

## Consequences

Positive:

- deterministic R2/R3 blocking remains explainable and testable without an LLM;
- every candidate can be traced to a confirmed revision, exact risk decision,
  reviewed template, plan, and validator output;
- users can compare bounded alternatives while keeping uncertainty visible; and
- queue outages, duplicates, cancellation, and worker loss have a durable
  recovery model rather than relying on browser state or broker memory.

Costs:

- more immutable records, foreign keys, audits, and migrations;
- outbox/lease/recovery workers require operational monitoring and failure
  exercises; and
- the product deliberately declines to provide an approval or physical-use
  outcome in this phase.

## Verification and operational requirements

- Test deterministic R2/R3 corpus cases and prompt-injection text that asks to
  lower risk or bypass policy.
- Test stale-input invalidation, direct-plan-bypass rejection, and worker gate
  rechecks before artifact persistence.
- Test two or three comparison children, mixed outcomes, full cancellation,
  concurrent final children, and cancellation racing a worker completion on
  SQLite and PostgreSQL.
- Exercise worker loss, broker outage, post-commit/pre-publish recovery,
  duplicate delivery, stale lease recovery, and bounded retry classification.
- Do not claim the Phase 5 operational durability exit gate until those
  recovery exercises and deployed worker-acknowledgement behavior are verified.
