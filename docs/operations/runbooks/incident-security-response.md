# Runbook: incident and security response

## Status and boundary

**Unexercised.** This is a source-level guide for suspected credential exposure,
private-object exposure, authorization bypass, malicious template behavior,
unsafe provider behavior, failed deletion, or hazardous-design report. It does
not create a monitored reporting address, legal authority, reviewer role, or
release approval. The current repository must not be treated as having a
configured external escalation contact until the project owner supplies one.

## Immediate stop and containment

1. Stop the affected operation. Do not continue provider calls, exports,
   template execution, object delivery, or destructive cleanup merely to gather
   more evidence.
2. Keep controlled-export flags disabled. Do not override risk, approval,
   quarantine, deletion, or audit state from a client or by direct database
   mutation.
3. Preserve safe evidence: timestamps, sanitized error category, affected
   component/version, synthetic IDs where applicable, and hashes. Do not retain
   raw prompts, credentials, access tokens, object URLs, participant data, or
   exploit payloads in public systems.
4. If a report concerns a potential hazard, use the supported containment path
   where authorized and preserve the report/audit record. Do not make a safety,
   fit, medical, or recall claim from this runbook.

## Triage and remediation

1. Classify the event conservatively: credential, access control, storage,
   deletion, provider, template/compiler, availability, or hazard.
2. Reproduce only in an isolated synthetic environment and only after the
   designated owner approves the scope. Do not test another user's project or
   a live production boundary.
3. Use a reviewed remediation path: revoke/rotate a compromised credential,
   contain the affected template or delivery path, restore a service from a
   known state, or pause the affected feature. Do not silently erase audit
   history or claim a fix before validation.
4. Add regression coverage and a sanitized change record before reopening the
   affected path. Keep unresolved privacy, safety, and operational questions
   visible to the designated owners.

## Record and escalate

Create a restricted incident record with the detection time, reporter channel,
scope, safe evidence, containment decision, owners, remediation status, and
follow-up date. Do not disclose vulnerability details publicly before an
authorized review. Escalate through the project owner's designated security,
privacy, technical, and safety channels once those channels exist.

## Completion criteria

An incident is not closed solely because service has resumed or a code change
has merged. Closure requires authorized review of containment, remediation,
regression evidence, communication obligations, and any remaining retention or
safety impact. This guide is not evidence of a completed incident drill.
