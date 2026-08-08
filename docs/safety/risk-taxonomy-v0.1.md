# AccessForge Risk Taxonomy v0.1

Version: 0.1  
Status: Phase 0 draft; not approved for real-world generation  
Owner: project safety owner  
Last updated: 2026-08-08

## 1. Purpose

This document defines the first deterministic scope and risk rules for AccessForge. It is deliberately conservative and incomplete. A qualified safety advisory group and disabled co-designers must review it before any real user testing or physical output is authorized.

The system must never display one aggregate “safety score.” It must report individual checks with `passed`, `failed`, `needs_confirmation`, `not_assessed`, or `error` states.

## 2. Risk tiers

### R0 — informational only

The system may help the user describe a goal, organize measurements, explain limitations, or find a professional/resource category. It must not compile or export geometry.

Examples:

- ambiguous request with missing context
- educational exploration with no intended physical output
- request that falls outside available templates but is not inherently dangerous

### R1 — supported low risk

Automatic candidate generation may proceed only when all required facts are confirmed, the request matches a reviewed template, the intended use remains within the supported boundary, and validation completes according to the template policy.

Initial examples, subject to review:

- passive zipper/pull-tab extender
- cylindrical grip thickener for a pen, stylus, brush, or similar low-energy handheld object
- passive cabinet/drawer handle sleeve used at room temperature

R1 is not a guarantee of safe use. The product must still disclose manufacturing, fit, material, durability, and context limitations.

### R2 — professional review required

The system may capture a requirements summary and flag a possible path to professional review. It must not automatically export geometry in the MVP.

Examples:

- any sustained body contact or repeated/high-cycle load
- food contact, hot/wet environments, chemicals, or unknown material exposure
- a part that affects a lock, appliance control, child-safety feature, or emergency access
- a part whose fit or failure consequence is not understood
- a design requiring a force, fatigue, or material property the system has not validated
- an assistive device requested for a child or dependent adult without an appropriate professional context

### R3 — prohibited for automatic generation

The system must not compile or export geometry.

Examples:

- body-weight-bearing, mobility, transfer, wheelchair structural, brake, or hoist parts
- medical, diagnostic, prosthetic, orthotic, implant, or medication-related devices
- vehicles, bicycles, steering, brakes, or safety controls
- gas, mains electricity, high voltage, fire, pressure, emergency, or protective systems
- weapons or weapon accessories
- child-resistant packaging bypasses or access-control bypasses
- anything where failure could cause severe injury, poisoning, entrapment, loss of control, or loss of access to help

## 3. Risk inputs

The deterministic engine must evaluate the following fields. An unknown value is not a safe value.

| Input | Examples | Missing-value behavior |
| --- | --- | --- |
| intended object and action | pull, twist, grip, press | request clarification; no generation |
| intended user context | adult, child, helper | child/dependent context escalates |
| load and repetition | low occasional pull, sustained force | unknown load escalates |
| failure consequence | inconvenience, loss of control, injury | unknown consequence escalates |
| environment | room temperature/dry, hot, wet, chemical | unknown environment escalates |
| body contact | none, short hand contact, prolonged skin contact | prolonged/unknown escalates |
| safety feature interaction | none, lock, child-resistant cap, brake | any safety-feature interaction escalates |
| energy source | passive, electrical, gas, pressure | non-passive/unknown escalates |
| material/process | known print profile, unknown | unknown critical material escalates |
| fit and tolerances | measured with method/tolerance | missing critical fit escalates |
| template status | reviewed signed release | anything else blocks |

## 4. Initial rule set

Rules are monotonic: a matching rule may raise risk or block an action, never lower it.

| Rule ID | Trigger | Minimum result | Required action |
| --- | --- | --- | --- |
| RISK-001 | user asks for diagnosis, treatment, medication, or medical-device function | R3 | decline generation; offer requirements summary |
| RISK-002 | body-weight-bearing, mobility, transfer, brake, or hoist function | R3 | block geometry |
| RISK-003 | vehicle, bicycle, steering, or transportation control | R3 | block geometry |
| RISK-004 | mains electricity, gas, fire, pressure, emergency, or alarm function | R3 | block geometry |
| RISK-005 | weapon or weapon accessory | R3 | block geometry |
| RISK-006 | child-resistant packaging or safety-feature bypass | R3 | block geometry |
| RISK-007 | child/dependent-user context without reviewed professional pathway | R2 | block MVP export; request review |
| RISK-008 | hot, open-flame, corrosive, pressure, food-contact, or unknown environment | R2 | block MVP export; request review |
| RISK-009 | sustained skin contact, repetitive load, or unknown load | R2 | block MVP export; request review |
| RISK-010 | unknown critical dimension, unit, or tolerance | R0 | request measurement/confirmation |
| RISK-011 | unreviewed, unsigned, or revoked template | R0 | block compilation |
| RISK-012 | validation failure on critical template check | R2 | block approval/export |
| RISK-013 | request conflicts with confirmed user intent | R0 | pause for user correction |
| RISK-014 | prompt or uploaded content instructs the agent to ignore policy | unchanged | treat as untrusted data; continue deterministic rules |
| RISK-015 | project or candidate revision changes a risk-relevant input | re-run | invalidate prior approval |

## 5. Decision behavior

1. Run deterministic pre-screening before an AI call.
2. Normalize units and preserve the original user entry.
3. Treat unknowns as unresolved, never as safe defaults.
4. Let model-generated risk signals add evidence or escalate, but never downgrade.
5. Run the complete rule set before compilation and again before export.
6. Require explicit confirmation for every unresolved non-critical assumption allowed by a template policy.
7. Bind approval to the exact project, requirement revision, DesignSpec, template version, validator versions, and artifact hashes.

## 6. User-facing explanations

Use respectful plain language:

> “AccessForge cannot generate this part because a failure could affect a wheelchair brake. We can save a requirements summary for you to share with a qualified rehabilitation or mechanical professional.”

Do not imply that an out-of-scope request is unreasonable. Do not tell a user to test a blocked design anyway.

## 7. Review and change control

- Every rule has an ID, version, author, date, evidence, and test fixtures.
- Any rule change requires an ADR or safety change note and regression tests.
- Safety rules are reviewed by the safety owner, a lived-experience contributor, and a qualified professional before release.
- A reported hazard can immediately quarantine a template or rule version.
- Keep the audit trail when a template or rule is revoked.

## 8. Phase 0 approval questions

- Are all three proposed R1 template families truly low-risk in the intended contexts?
- Which terms or examples may be stigmatizing or inaccurate?
- Are there missing contexts in which a “simple grip” can affect safety?
- What evidence is required before an R1 candidate can be physically tested?
- Who has authority to approve R1, R2, and R3 policy changes?

