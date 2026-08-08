# AccessForge Governance

Status: proposed for the pre-alpha period  
Last updated: 2026-08-08

## Roles

- **Project owner:** final authority for scope, funding, legal review, and release approval.
- **Technical maintainer:** owns implementation quality, architecture, CI, and release mechanics.
- **Safety owner:** owns the risk taxonomy, incident response, template quarantine, and safety release gate.
- **Lived-experience contributors:** disabled co-designers whose feedback can change product scope, language, interaction, and safety policy.
- **Professional reviewers:** qualified accessibility, rehabilitation, mechanical, privacy, or security reviewers consulted within their expertise.

One person may hold multiple roles initially, but safety decisions should receive independent review as soon as practical.

## Decision process

- Product and architecture decisions are recorded as ADRs or decision notes.
- Risk-rule, template, public-claim, and data-policy changes require explicit review labels.
- A credible hazard may quarantine a template or release immediately; investigate and document afterward.
- Contributors can challenge a decision with evidence, lived experience, or a safety concern.
- The project owner decides unresolved product scope; the safety owner may block a release on safety grounds.

## Release gates

No release that handles real user data or generates physical artifacts is allowed until the applicable Phase exit gate, safety review, privacy review, accessibility review, and test evidence are recorded.

## Community templates

Hosted production executes only reviewed, signed template releases. A contributor must provide the template’s intended use, prohibited use, parameter ranges, material/process assumptions, tests, known limitations, license, and provenance. Maintainers can revoke a template and must preserve the audit trail.

## Conflicts of interest

Reviewers should disclose financial, employment, or personal interests that could affect a safety or release decision. The project may seek an additional reviewer when a conflict matters.

## Changes to this policy

Update this document through a reviewed pull request and record the rationale in `docs/architecture/` or a decision note.

