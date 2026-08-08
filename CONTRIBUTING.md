# Contributing to AccessForge

AccessForge is in Phase 0. The first contribution is careful review of the product boundaries, research plan, safety model, privacy model, and accessibility requirements.

## Before contributing

Read:

- `master-prompt.md`
- `docs/safety/risk-taxonomy-v0.1.md`
- `docs/privacy/threat-model-and-data-flow.md`
- `docs/accessibility/acceptance-checklist.md`
- `SECURITY.md`

Do not submit real participant media, private health information, provider API keys, or designs intended for safety-critical use.

## Good early contributions

- identify an unsafe or ambiguous scope rule
- improve respectful and accessible language
- add a synthetic user journey or test case
- review threat-model controls
- improve documentation clarity
- propose a template only with its use limits, material/process assumptions, validation plan, license, and evidence

## Pull-request expectations

Explain:

- the user problem and scope
- what changed and what did not change
- safety/privacy/accessibility impact
- tests or review performed
- migration/deployment impact
- whether the change affects a template, risk rule, model prompt, or public claim

Do not weaken a safety rule, hide an unassessed property, or make a model response appear deterministic without evidence.

Until the license and contribution terms are finalized, external code and template contributions require maintainer approval before merge.

