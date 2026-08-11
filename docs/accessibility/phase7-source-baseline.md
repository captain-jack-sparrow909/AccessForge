# Phase 7 Accessibility Source Baseline

Status: source-level safeguards implemented; browser, assistive-technology, and pilot evidence not yet collected
Last updated: 2026-08-09

## Purpose

This record describes what can be checked from the repository without claiming WCAG conformance or participant validation. It is a starting point for Phase 7, not an audit result.

## Automated source check

Run either command from the repository root:

```sh
pnpm --filter @accessforge/web test:accessibility-source
pnpm --filter @accessforge/web test
```

The Vitest source-contract check verifies that:

- the `model-viewer` integration is dynamically imported, is explicitly user-requested, and does not contain automatic rotation;
- the structured candidate report occurs before the optional 3D preview in source;
- capture uses visible native file inputs with linked explanatory text rather than visually hidden upload controls;
- visible-focus, reduced-motion, forced-colors, and wrapping primary-navigation safeguards remain in the shared source.

These are regression checks over source text. They do not prove the browser's accessibility tree, focus order, third-party viewer behavior, color contrast, responsive reflow, upload performance, or a user's experience.

## Evidence still required

Before any accessibility/pilot exit decision, record dated evidence for each of the following in the acceptance checklist or a non-identifying remediation log:

- axe or equivalent browser-based scan of representative authenticated and unauthenticated routes;
- keyboard-only completion of the text-only/no-camera/no-audio workflow, manual measurements, candidate review without opening 3D, and fail-closed export/hazard paths;
- VoiceOver/Safari and NVDA/Chrome (or documented equivalent) checks of labels, error/status announcements, headings, and optional viewer behavior;
- 200% zoom, 320 CSS-pixel reflow, forced colors/high contrast, reduced motion, touch-only, low-end device, and slow-network checks;
- compensated, authorized sessions with diverse disabled participants under the approved research and privacy process;
- a public remediation log that excludes participant-identifying information and names an owner/status for each finding.

No unchecked checklist item should be changed to complete based only on this source baseline.
