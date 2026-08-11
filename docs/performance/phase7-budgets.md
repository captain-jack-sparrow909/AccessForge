# Phase 7 performance budgets

Status: source-level release budgets; no browser or field-data pass is claimed

Last updated: 2026-08-11

These budgets make the low-end-device and slow-network acceptance boundary
explicit. They are release gates for a future approved deployment, not evidence
that the current source meets them. Measure authenticated routes only with
approved synthetic projects and without production credentials.

## Required measurement profiles

1. **Field profile:** report mobile and desktop separately at the 75th
   percentile. Each core route must have LCP at or below 2.5 seconds, INP at or
   below 200 milliseconds, and CLS at or below 0.1.
2. **Low-end lab profile:** exercise a clean-storage mobile navigation with Slow
   3G network throttling and 6x CPU slowdown. Record the exact browser,
   hardware, route, build revision, cache state, and tool version.
3. **Real-device profile:** at least one representative low-memory Android
   phone and one iOS device complete the core workflow on a constrained network.
   A simulator alone cannot satisfy this profile.

Lighthouse is simulated evidence and must be paired with real-device and field
data. A median-only report cannot replace the required 75th-percentile field
view.

## Core route budgets

Apply these provisional transfer ceilings to `/sign-in`, `/dashboard`, project
overview, consent, capture, measurements, requirements, risk, candidate report,
and deletion status on a cold first navigation. Record compressed network bytes,
not source-map or uncompressed build-directory sizes.

| Resource | Cold-route ceiling |
| --- | ---: |
| JavaScript required before the core route is usable | 250 KiB |
| CSS required for the route | 100 KiB |
| HTML plus React Server Component payload | 150 KiB |
| Total initial compressed transfer, excluding explicitly user-selected media | 500 KiB |

The budgets are fail-closed: a missing measurement, failed trace, unexpected
third-party request, or value over a ceiling blocks a performance sign-off. A
larger limit requires a dated, reviewed decision and participant-impact notes;
it must not be silently updated to fit the current build.

## Interaction and optional-media constraints

- A control acknowledges activation visually within 100 milliseconds, even
  when its network operation continues behind a busy/status message.
- Text-only observation, manual measurements, structured candidate reports, and
  deletion status must not download camera, video, GLB, or model-viewer bytes.
- The model-viewer implementation and private GLB are requested only after the
  user selects **Load optional interactive 3D preview**. Hiding it must leave the
  structured report usable; reopening may use normal browser caching.
- A failed or slow optional preview cannot delay, replace, or erase the primary
  structured report.
- No core task may require hover, fine-pointer input, animation, or a continuously
  running render loop.

## Evidence required before Phase 7 exit

For every core route, retain a sanitized table of the build revision, profile,
sample size, LCP/INP/CLS, transfer totals, long-task findings, failures, and
remediation link. Run bundle analysis when a route exceeds a ceiling, but treat
the route trace and downloaded resource sizes as the acceptance evidence.

The repository source test currently protects only one prerequisite: the heavy
3D dependency remains behind an explicit dynamic import. Browser measurements,
real-device checks, field percentiles, and participant impact remain open.

## References

- [Web Vitals thresholds and 75th-percentile guidance](https://web.dev/articles/vitals)
- [Chrome Lighthouse mobile and throttling guidance](https://developer.chrome.com/docs/devtools/lighthouse/)
- [Next.js package-bundling and analyzer guidance](https://nextjs.org/docs/app/guides/package-bundling)
