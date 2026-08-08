# AccessForge Product Requirements

Version: 0.1  
Status: Phase 0 draft  
Last updated: 2026-08-08

## 1. Product statement

AccessForge helps a person who has difficulty interacting with a physical object co-design a personalized assistive adapter that can be manufactured from a reviewed parametric template.

The product captures the user’s intent and constraints, makes assumptions visible, proposes bounded designs, runs deterministic checks, and provides reproducible CAD artifacts with explicit limitations.

AccessForge is not a medical-device manufacturer, diagnostic product, therapy tool, safety-certification service, or replacement for professional assessment.

## 2. Problem

Many ordinary objects are usable in principle but difficult to operate because of grip diameter, pull geometry, reach, friction, pinch force, or the interaction required. Existing options often force a person to choose between generic aids, expensive custom fabrication, poorly documented DIY designs, and abandoning the object.

The hard part is not simply producing a 3D shape. A useful system must preserve the person’s own goal, distinguish facts from assumptions, avoid unsafe use cases, produce editable geometry, and explain what was checked.

## 3. Target users

### Primary co-designer

A disabled person, older adult, or person with temporary or situational limited dexterity who wants to accomplish a specific low-risk interaction. They may work alone or invite a trusted helper.

### Secondary co-designer

A family member, support worker, maker, occupational therapist, rehabilitation engineer, or accessibility practitioner helping the primary user. They may contribute observations, but the primary user’s preferences and approval remain visible.

### Template maintainer

A technically competent contributor who creates or reviews a parametric template and its limits, fixtures, tests, manufacturing guidance, license, and safety policy.

### Safety or professional reviewer

A qualified reviewer who can block a use case, raise a risk tier, annotate a design, or approve a future professional-review workflow. Professional review is not part of the automatic MVP.

## 4. Jobs to be done

- “Help me explain exactly what is hard about this interaction.”
- “Help me provide enough measurements without forcing me to repeat a painful action.”
- “Show me options I can understand and adjust.”
- “Tell me what was checked, what was assumed, and what was not assessed.”
- “Let me keep control of my private media and delete it.”
- “Give me an editable file I can take to a maker or fabricator.”

## 5. MVP scope

The MVP supports only passive, non-load-bearing, low-energy grip and pull aids used at room temperature.

### Supported template families

1. Zipper or pull-tab extender
2. Pen, stylus, brush, or similar cylindrical grip thickener
3. Cabinet or drawer handle grip sleeve

The MVP supports text descriptions, still images, optional short video, a printable fiducial marker for scale, and manual measurements. Automatic photogrammetry, force estimation, finite-element analysis, raw-image model calls, and professional certification are deferred.

### MVP outputs

- Editable requirements and measurement record
- One or more reviewed-template candidates
- Interactive 3D preview plus structured text alternative
- STEP, STL, GLB, and a machine-readable DesignSpec when generation succeeds
- Validation report listing passed, failed, needs-confirmation, and not-assessed checks
- Plain-language manufacturing and limitation notes
- Provenance manifest and artifact hashes

## 6. Non-goals and hard exclusions

AccessForge must not automatically generate or export:

- medical, diagnostic, therapeutic, prosthetic, orthotic, implant, or medication-related devices
- wheelchair structural components, transfer equipment, hoists, ramps, body-weight-bearing parts, or mobility safety components
- vehicle, bicycle, brake, steering, or transportation-control parts
- gas, mains electricity, high voltage, fire, emergency, alarm, protective, or lock-bypass components
- weapons or weapon accessories
- child-resistant packaging, child-safety systems, or products intended for unsupervised children
- hot-surface, open-flame, pressure, corrosive-chemical, food-contact, or long-duration skin-contact parts
- any part where failure could cause injury, entrapment, poisoning, loss of control, or loss of access to help

Out-of-scope requests may receive a requirements summary and a respectful explanation. They must not receive generated geometry.

## 7. Core user journey

1. User reads the supported-use and privacy summary.
2. User creates a private project and selects whether they are the primary co-designer or a helper.
3. User describes the desired outcome in their own words.
4. Deterministic pre-screening checks whether the request is in MVP scope.
5. User gives separate consent for text, images, video, helper participation, and optional community sharing.
6. User chooses a text-only, still-image, or guided-capture path.
7. User records measurements, methods, tolerances, and unknowns.
8. AI suggests structured requirements and clarifying questions; the user edits and confirms them.
9. Deterministic rules assign a risk tier and show the evidence.
10. A reviewed template is selected and bounded candidate parameters are proposed.
11. Deterministic CAD compilation and validation run in a background worker.
12. User compares candidates using both the viewer and a structured alternative.
13. User adjusts allowed parameters or answers another question; changed inputs create a new revision.
14. User explicitly approves one immutable candidate.
15. Export reruns scope, risk, and validation checks, then produces the artifact bundle.
16. User can report fit, discomfort, breakage, near misses, or unsafe output and delete their data.

## 8. Functional requirements

### FR-001 Project and consent

Create private projects with explicit ownership, participant roles, consent records, retention choices, and audit events.

### FR-002 Accessible observation

Support text-only observation, still-image upload, optional video, helper mode, captions/transcripts, and manual alternatives. Never require a painful or unsafe repeated action.

### FR-003 Measurement provenance

Every measurement stores value, canonical unit, original entry, method, tolerance, source, confidence, confirmation state, timestamp, and revision.

### FR-004 Requirement confirmation

AI-generated requirements are suggestions until the user confirms or edits them. Every field displays its provenance and unresolved assumptions.

### FR-005 Scope and risk

Deterministic pre- and post-generation rules can block, escalate, or request confirmation. AI cannot lower risk.

### FR-006 Reviewed templates

Only reviewed and signed template versions can execute in hosted production. Template contracts reject missing or out-of-range parameters.

### FR-007 Reproducible generation

A fixed DesignSpec, template version, generation seed, and supported build environment produce equivalent geometry and a provenance manifest.

### FR-008 Validation transparency

Every check has a version, status, evidence, threshold, limitation, and remediation. A passed check is not presented as a safety certification.

### FR-009 Human approval

Export requires approval of the exact candidate revision after all relevant checks pass or are explicitly acknowledged according to policy.

### FR-010 Privacy controls

Users can view, export, retain, or delete project data. Source media is private by default and never used for training without separate opt-in.

### FR-011 Feedback and incident reporting

Users can report poor fit, discomfort, breakage, near misses, or hazards. Maintainers can quarantine a template version and notify affected users.

## 9. Non-functional requirements

- WCAG 2.2 AA target for all routes and responsive variations.
- Core manual workflow works without an AI key.
- API objects are authorized server-side by project/organization membership.
- Heavy jobs run outside Vercel request functions.
- Private media uses time-limited presigned URLs and object-store encryption.
- Every state transition and export decision is auditable.
- P95 non-job API response target: under 500 ms in staging for simple authenticated reads; generation is asynchronous and excluded.
- A user can cancel a queued job and see a clear retry/failure state.
- No sensitive media or API keys are sent to analytics, logs, traces, or error trackers.

## 10. MVP acceptance scenarios

### Supported scenario

A user needs a larger grip for a pen. They can enter a preferred grip diameter manually, choose a cylindrical grip template, review three candidate thicknesses, inspect validation findings, approve one, and download a reproducible artifact bundle.

### Accessible alternative scenario

A user cannot hold a phone steady or speak. They can complete the same flow with text, still images or no media, keyboard navigation, manual measurements, captions, and a structured design report.

### Out-of-scope scenario

A user requests a wheelchair brake component. The system assigns R3, explains that it will not generate the component, preserves only the user-approved requirements summary, and provides a path to seek qualified professional help.

### Revision scenario

A user changes the target diameter after approving a candidate. The old approval cannot authorize the new revision. The system creates a new DesignSpec, recompiles, revalidates, and asks for approval again.

## 11. Open product questions

- Which first template family produces the clearest physical benefit while remaining genuinely low risk?
- What measurement burden can participants tolerate for each template family?
- Which materials and print processes are acceptable for the initial physical test fixtures?
- What language do disabled participants prefer for describing access needs and limitations?
- Should the hosted MVP offer public accounts before a vetted pilot, or remain invite-only?

