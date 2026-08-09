# ADR-0009: Phase 6 controlled approval, export, and hazard containment

Status: proposed — fail-closed Phase 6 source foundation implemented; no current
template release or deployment is approved for controlled export
Date: 2026-08-09

## Context

Phase 5 can create private, software-only candidate artifacts after a current
deterministic R1 risk decision. It deliberately stops before approval, export,
manufacture, or physical-use claims. Phase 6 is the first proposed boundary
for a controlled artifact bundle and for recording limited, non-human protocol
evidence. It must not turn a successful compiler run, a passing software check,
or a user preference into an assertion about a physical outcome.

The current repository template releases are synthetic-development-only
releases. They are not approved for real-world output, controlled testing, or
participant use. The source foundation implements the records and server gate
described here, but its deployment flags default to false and current template
validation blocks the path. It does not authorize a live export path or
physical work.

## Decision

### Fail closed before approval or bundle release

An approval is a server-owned, immutable record authorizing a narrowly defined
software operation: creation of a private, hash-verified artifact bundle for
one exact candidate. It is not a professional determination, certification,
manufacturing authorization, or statement about safety, fit, comfort,
strength, accessibility benefit, printability, material suitability, or any
physical outcome.

The server must deny approval and export unless every required condition is
true at the time of the request and again immediately before a bundle is made
available:

- the project is in the expected review state and the caller has the required
  project role;
- the candidate is a completed, private candidate with complete immutable
  artifact and provenance hashes;
- a current R1 risk assessment, plus the independent Phase 6 gate, remains
  current for the exact candidate;
- the exact confirmed requirements revision, risk-bound DesignSpec revision,
  reviewed template release, candidate, validation run, and artifact hashes
  match the proposed approval context;
- all mandatory deterministic validation checks have the required recorded
  outcome; any `needs_confirmation` or `not_assessed` finding denies the gate
  rather than being silently waived;
- the required controlled-protocol evidence is complete for the selected
  template/policy version, if a policy permits a protocol at all;
- no relevant hazard, recall, quarantine, revocation, deletion, expired
  authorization, or policy-version mismatch is active; and
- an explicitly authorized human has acknowledged the plain-language checks,
  limitations, and bundle scope. The acknowledgement does not substitute for
  evidence or change a risk tier.

No browser-supplied status, candidate hash, risk tier, template version,
protocol result, or approval assertion is trusted. Missing data, an unknown
policy, a failed check, a stale value, a conflicting record, or an unavailable
dependency denies the operation. There is no permissive fallback.

Until an implementation has passed its operational gates, deployment policy,
template status, and the server gate keep controlled export false. No current
route can return a downloadable CAD, mesh, slicer, archive, or equivalent
artifact bundle.

### Seal the approval context and preserve lineage

Create an immutable `ApprovalContext` (or equivalently named server record)
from canonical hashes, immutable IDs, and policy versions rather than mutable
project fields. Its minimum lineage is:

```text
confirmed RequirementRevision
  -> immutable RiskAssessment + ruleset version/hash
  -> risk-bound DesignSpecRevision + reviewed template release/hash
  -> DesignPlan / CandidateGenerationBatch / CandidateDesign
  -> CandidateValidationRun + immutable private artifact hashes
  -> controlled-protocol definition/version + accepted evidence hashes
  -> ApprovalContext + acknowledgement record
  -> one bundle manifest + bundle hash + authenticated delivery request
```

The approval context stores the exact candidate and artifact-manifest hashes,
requirements revision, risk assessment input/decision/ruleset hashes, DesignSpec
hash, template manifest hash, validation report hash, protocol definition hash,
accepted-evidence hashes, and policy version. It also records who performed
which software action and when, without placing credentials or raw sensitive
content in the audit log.

Approvals, evidence acceptances, and bundle manifests are append-only. A later
correction creates a new revision and a new context; it never rewrites history.
Every risk-relevant project edit, requirements revision, template release
change/revocation, candidate replacement, validation change, evidence change,
hazard report, policy change, or authorization expiry invalidates affected
contexts and blocks future authenticated delivery. Invalidating a context does
not erase the historical record; it records the reason and prevents use of the
old record. Bytes already delivered to a client cannot be recalled, so the
source never emits an independent object-store bearer URL for an export bundle.

### Re-validate at the point of release

Export must be a two-step server operation, not a static object URL or a
client-side archive:

1. A preflight derives a fresh proposed context from current durable records
   and returns the exact blockers and visible limitations. It does not create
   an approval as a side effect.
2. After the required acknowledgement, the server re-reads and locks the
   relevant records, re-runs the deterministic policy and validation checks,
   compares all sealed hashes, and atomically records a bundle manifest.
   Only then may it fulfill an authenticated, no-store API download request;
   the API rechecks the exact current gate before streaming bytes and never
   hands the browser a raw object-store URL.

The bundle contains only server-selected immutable artifacts and a
plain-language report that identifies the exact revisions, measured software
checks, unassessed properties, protocol-evidence status, hashes, and any
active limitations. It must not include unreviewed executable code, secrets,
raw credentials, another project's data, or claims beyond the recorded
software/protocol facts. The server verifies the stored ZIP size, archive
SHA-256, fixed layout, and manifest hash before delivery; clients can verify
the bundle contents against the included manifest.

If a record changes or a hazard arrives between preflight and delivery, every
future authenticated delivery request fails closed. Retrying starts from fresh
state and creates a new audit event; it never resurrects an old approval.

### Record controlled non-human protocol evidence conservatively

Phase 6 may support only a versioned, predeclared protocol for non-human
dimensional fixtures and material/process coupons. A protocol definition must
state its template scope, allowed equipment and calibration references,
measurement method and units, acceptance-record schema, stop conditions,
required attachments, retention, reviewer roles, and known limitations.
It must be reviewed and enabled by an explicit server policy before any
evidence can be accepted.

Evidence is a record of what was observed under the protocol, not a conclusion
about a person or a physical design's suitability. Accepted evidence requires
the exact protocol version, candidate/bundle lineage, controlled vocabulary
outcome, source hash, timestamp, operator/reviewer role, and any applicable
instrument/calibration identifiers. Values retain units, tolerance, method,
and uncertainty; the system must reject silent unit conversion, free-text
reinterpretation, and evidence attached to a different candidate or protocol.

The current source foundation accepts only typed record metadata and immutable
evidence hashes from a configured reviewer role. It does **not** accept
evidence uploads, scan attachments, or verify the real-world provenance of a
hash. Those capabilities remain operational requirements and cannot be
represented by seeded or synthetic records to open the gate.

If evidence uploads are added later, they enter an untrusted quarantine state. They are size,
content-type, checksum, malware/format-safety, access-control, and retention
checked before a reviewer can reference them. A failed, missing, ambiguous, or
quarantined item cannot satisfy a protocol requirement. Original evidence is
kept private and immutable; derived display representations are separately
tracked and never replace the source hash.

No Phase 6 protocol may collect, infer, or decide a participant's fit,
comfort, medical condition, ability, or safety outcome. Any future
participant-facing study requires its own consent, privacy, accessibility,
ethics, and operational approvals outside this protocol boundary.

### Make feedback, hazards, and quarantine first-class containment records

Provide a separately authorized feedback intake for reported fit, comfort,
breakage, and near-miss observations. These reports are user-provided reports,
not verified findings. They are immutable at intake, access-controlled,
minimized for sensitive content, and linked to the exact candidate/bundle when
known. A correction or follow-up appends a new record rather than editing the
original report.

Define a deterministic containment policy with at least these effects:

- a potentially hazardous, breakage, or near-miss report creates a review case
  and immediately blocks new approvals and delivery authorizations for the
  affected candidate, template release, or policy scope until resolved by the
  defined operational process;
- an evidence-integrity, malware, or provenance concern quarantines the
  associated upload and prevents it from supporting approval;
- a template or policy concern can revoke a release for future bundles while
  preserving immutable historical references; and
- an affected-output registry records which bundle manifests and delivery
  authorizations may require follow-up. Notifications, if configured, are
  audited attempts rather than a claim that every recipient was reached.

The system must expose a plain-language status for the reporter and project
owner without disclosing another person's private report. Clearing quarantine
or containment requires an authorized, auditable decision linked to the
evidence and policy version; it cannot be performed by an AI model, a browser
flag, or an artifact download request.

### Keep AI and asynchronous systems outside the authority boundary

Models may summarize already accepted records for a human-facing report, but
they cannot create an approval, accept protocol evidence, clear quarantine,
lower risk, select a policy, bypass validation, or issue delivery credentials.
Their outputs are untrusted explanatory text and must retain visible
limitations.

PostgreSQL remains the source of truth. Broker messages contain only durable
IDs, and release, quarantine, notification, and retention jobs use idempotent
state transitions and durable audit/outbox records. A worker retry must
re-read sealed context and containment state before any side effect. Loss of a
broker, scanner, object store, or policy dependency blocks the operation; it
does not create an untracked download link or a partial bundle.

## Explicit non-goals

This ADR does not:

- enable a real export, manufacturing workflow, participant use, or controlled
  physical testing while all template releases remain synthetic-only;
- treat a bundle, software validation, protocol record, acknowledgement, or
  feedback report as a safety certification, professional approval, or
  authorization for physical use;
- establish or infer fit, comfort, strength, durability, printability,
  material behavior, accessibility benefit, regulatory compliance, or any
  real-world performance characteristic;
- accept uploaded model code, slicer code, community templates, arbitrary
  archives, or executable instructions as protocol evidence or bundle content;
- allow an AI model, a client, a queue message, or a mutable field to override
  risk, validation, protocol, containment, or approval policy; or
- replace future accessibility pilots, qualified review, privacy review,
  security review, or legal/regulatory work required for a broader release.

## Alternatives considered

- **Let a user download after a successful candidate job:** rejected because a
  compiler completion does not seal current risk, validation, containment, or
  provenance state.
- **Treat a signed acknowledgement as approval:** rejected because it does not
  establish that required deterministic checks or protocol records exist.
- **Use mutable project status as the export gate:** rejected because later
  revisions and hazards need precise invalidation and historical lineage.
- **Accept free-form photos, notes, or user feedback as passing protocol
  evidence:** rejected because their source, units, conditions, and scope are
  not controlled enough to support the gate.
- **Delete or overwrite hazardous records to remove them from view:** rejected
  because containment and recall work require immutable history and auditable
  follow-up.

## Consequences

Positive:

- release decisions are reproducible from sealed, inspectable records;
- stale revisions, missing evidence, and hazards block the narrow release path
  before private artifacts are delivered;
- feedback and suspected hazards can contain affected scope without silently
  losing provenance; and
- current synthetic-only templates remain unable to drift into a real-output
  path by UI copy or client-side state alone.

Costs:

- Phase 6 requires new immutable records, policy/version management, access
  control, quarantine scanning, retention, audit, and notification operations;
- every revision and hazard must propagate invalidation across related
  approvals and delivery authorizations; and
- the system will decline many requests until an explicit policy and complete
  operational evidence exist.

## Verification and operational requirements

- Test every fail-closed branch: stale revision, changed risk context, failed
  or unknown validation, missing/invalid/quarantined evidence, expired role,
  revoked template, policy mismatch, scanner/object-store outage, and active
  hazard.
- Test concurrent approval/export attempts, preflight-to-release races,
  duplicate job delivery, cancellation, worker loss, and a hazard arriving
  during bundle construction.
- Test that a bundle manifest and every contained artifact hash verify, while a
  modified, incomplete, cross-project, or stale bundle is rejected.
- Test evidence schema/unit validation, source-hash preservation, quarantine
  transitions, access control, retention/deletion behavior, and append-only
  corrections.
- Exercise containment and affected-output follow-up with synthetic fixtures;
  record delivery attempts without claiming real-world recall completion.
- Do not claim the Phase 6 exit gate, controlled physical tolerance outcome,
  approval/export availability, or a public MVP until the required policies,
  deployed operational controls, and independently reviewed evidence exist.
