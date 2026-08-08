# AccessForge Metrics and Physical-Test Assumptions

Version: 0.1  
Status: Phase 0 draft  
Last updated: 2026-08-08

## 1. Measurement principles

Do not optimize for GitHub stars, generated-file count, or AI call volume. Measure whether people can accomplish a useful low-risk task, understand limitations, and remain in control.

Never collect disability or health-related analytics. Use aggregate, opt-in research identifiers and synthetic/demo projects for technical telemetry.

## 2. Product metrics

| Metric | Definition | Initial target | Evidence source | Owner |
| --- | --- | --- | --- | --- |
| requirements completion | invited participant completes requirements review without researcher intervention | baseline in Phase 7, improve thereafter | moderated usability task | research/product |
| user correction rate | AI-proposed requirement fields edited or rejected by user | measure, do not optimize toward zero | product events with consent | product |
| clarification burden | median number of questions before confirmation | measure by template family | project audit events | product |
| first-prototype fit | participant reports that the physical candidate meets intended low-risk interaction in controlled test | target set after baseline | physical test + participant feedback | safety/product |
| limitation comprehension | participant correctly identifies assessed and unassessed properties | 90% in moderated testing before public pilot | comprehension check | research |
| time to candidate | confirmed requirements to candidate report excluding queue outage | baseline by template | job/audit events | engineering |

## 3. Safety metrics

| Metric | Definition | Target |
| --- | --- | --- |
| prohibited generation escape | R3 request reaches CAD compiler/export | zero |
| risk downgrade escape | model/tool causes a lower deterministic tier | zero |
| approval revision mismatch | export succeeds for a revision other than approved exact revision | zero |
| critical validator bypass | failed critical check reaches export | zero |
| serious incident | reported output plausibly causes injury or dangerous loss of control | zero; immediate investigation |
| hazard response | time from credible report to template quarantine | define SLA before pilot |

## 4. Accessibility metrics

- completion of text-only/no-camera/no-audio core workflow
- keyboard-only completion
- screen-reader completion
- high-contrast/forced-colors completion
- reduced-motion completion
- task failure and recovery rate by accommodation path
- severity and recurrence of accessibility defects
- participant-reported burden and dignity of language

Set numeric targets after Phase 0 co-design rather than inventing a universal disability baseline.

## 5. Privacy/security metrics

- percentage of private assets delivered only through authorized time-limited URLs
- deletion jobs completed within the declared retention policy
- secret-redaction test coverage
- cross-project authorization denial rate in negative tests
- number of provider calls containing raw media (target zero in MVP)
- number of unapproved community publications (target zero)
- time to revoke a compromised provider key or template release

## 6. Reliability/operations metrics

- API P95 latency for simple authenticated reads
- queue wait and job execution time by job type
- job success/failure/retry/cancel rates
- provider timeout and rate-limit rates
- CAD worker memory/CPU/timeouts
- artifact hash/reproducibility failures
- backup/restore and deletion-drill outcomes

## 7. Assumption register

Each assumption must have an owner, an evidence method, a decision deadline, and a consequence if false.

| ID | Assumption | Risk if false | Evidence needed | Phase |
| --- | --- | --- | --- | --- |
| A-001 | People can describe a target interaction without naming a diagnosis. | consent and requirement flow becomes intrusive | co-design interviews | 0 |
| A-002 | The three template families cover a useful first set of low-risk tasks. | MVP has no meaningful benefit | participant ranking and pilot | 0/7 |
| A-003 | Manual measurements are acceptable when automatic capture is unavailable. | users abandon workflow | usability sessions | 0/2 |
| A-004 | A printable fiducial marker is usable for scale by the intended audience. | capture is inaccurate or inaccessible | assisted capture test | 2/7 |
| A-005 | Cylindrical grip and handle-sleeve parameters can be bounded conservatively. | candidate fit or durability is unreliable | CAD fixtures and physical coupons | 4/6 |
| A-006 | The chosen material/process profile is appropriate for low-risk room-temperature use. | failure or discomfort | material/process review and coupons | 4/6 |
| A-007 | Users understand validation limitations when shown itemized findings. | false confidence | comprehension testing | 5/7 |
| A-008 | AI improves organization without increasing harmful assumptions. | users trust incorrect requirements | fake-provider and pilot evaluation | 3/7 |
| A-009 | The default provider can produce structured outputs within the workflow budget. | AI feature is unavailable or costly | provider contract tests | 3 |
| A-010 | Source media can be processed without sending raw media to a model provider. | privacy boundary is violated | architecture and integration test | 2/3 |
| A-011 | Sandboxed template execution can meet job latency and resource limits. | hosted worker is exploitable or uneconomical | adversarial fixtures and load test | 4/8 |
| A-012 | A revocation workflow can notify users of a hazardous template. | known risk remains in circulation | tabletop exercise | 6/8 |
| A-013 | The legal/product boundary remains outside regulated medical-device claims. | launch claims and liability change | jurisdictional legal review | 0/11 |

## 8. Physical test plan outline

Before participant testing, test deterministic geometry and print/process behavior using non-human fixtures:

1. Verify dimensions against calibrated tools.
2. Produce a small set of print coupons across intended orientations and material profiles.
3. Measure fit, surface defects, dimensional drift, and breakage under the bounded intended action.
4. Record printer, nozzle/process, material batch, orientation, layer settings, humidity, and test method.
5. Define stop criteria for cracks, sharp edges, unexpected deformation, detachment, or fit failure.
6. Have the safety reviewer approve the physical protocol before using participant-specific outputs.

The initial physical protocol must not use medical, hot, chemical, electrical, load-bearing, or safety-critical objects.

