# AccessForge Accessibility Acceptance Checklist

Version: 0.1  
Status: Phase 0 draft  
Target: WCAG 2.2 AA plus lived-experience review  
Last updated: 2026-08-08

This is a product acceptance checklist, not a claim of conformance. Conformance requires testing the complete implemented experience, including responsive variations and any third-party components.

## 1. Non-negotiable workflow alternatives

For every core task, provide an equivalent path that does not require:

- camera or video
- microphone or speech
- hearing audio
- holding a phone steady
- two hands
- a mouse or trackpad
- dragging or swiping
- repeated or painful physical movement
- interpreting a 3D scene without text

Required alternatives:

- text-only description
- still-image upload instead of video
- manual measurement instead of automatic measurement
- helper/co-designer mode with participant consent
- captions/transcript for every instructional video/audio
- structured candidate report and static preview alongside 3D viewer

## 2. Perceivable

- [ ] Every informative image, diagram, 3D preview, and status icon has an appropriate text alternative.
- [ ] Decorative images are ignored by assistive technology.
- [ ] Instructional video has captions; audio instructions have transcripts.
- [ ] Color is never the only signal for risk, validation, progress, or errors.
- [ ] Text and controls meet contrast requirements in default and high-contrast modes.
- [ ] Content reflows at narrow widths and large text/zoom without loss of function.
- [ ] Focused elements remain visible at high zoom.
- [ ] Motion can be reduced or disabled; no essential information depends on animation.
- [ ] Error summaries and progress updates are announced appropriately.

## 3. Operable

- [ ] All routes and dialogs are keyboard operable.
- [ ] Focus order is logical and focus is not trapped unexpectedly.
- [ ] No keyboard trap exists in capture, measurement, viewer, or export flows.
- [ ] Drag-only controls have keyboard and numeric alternatives.
- [ ] Targets have sufficient size and spacing for touch and motor access.
- [ ] Long-running jobs have pause/cancel/retry behavior that is accessible.
- [ ] Time limits are avoidable or extendable.
- [ ] Authentication and upload workflows work with password managers and assistive technology.
- [ ] Users can skip repeated instructions and navigate by headings/landmarks.

## 4. Understandable

- [ ] Page titles, headings, labels, and instructions are descriptive and consistent.
- [ ] The product explains what is supported before asking for private data.
- [ ] Units, tolerances, and measurement methods are explained in plain language.
- [ ] Errors identify the field, problem, consequence, and recovery action.
- [ ] Risk explanations are respectful and do not imply blame.
- [ ] AI suggestions are visually and semantically distinguished from user-confirmed facts.
- [ ] Approval and export are deliberate, reversible until final action, and describe the exact revision.
- [ ] Help text is available without forcing a user to lose entered data.

## 5. Robust

- [ ] Semantic HTML and accessible names are present before visual styling.
- [ ] Screen-reader testing covers at least VoiceOver/Safari and NVDA/Chrome or equivalent environments.
- [ ] Components expose correct roles, states, values, and relationships.
- [ ] Dynamic job progress and validation results are announced without excessive interruption.
- [ ] Browser zoom, OS text scaling, reduced motion, forced colors, and touch input are tested.
- [ ] API errors have accessible frontend representations and are not exposed only in console logs.

## 6. Capture and measurement-specific checks

- [ ] The user can skip capture and start with a text description.
- [ ] Instructions never ask the user to repeat an action that causes pain or fatigue.
- [ ] The fiducial-marker step has a manual-scale alternative.
- [ ] Camera permission denial has a complete recovery path.
- [ ] Upload progress includes text status and does not rely only on animation.
- [ ] Measurements support keyboard entry, unit conversion, tolerances, correction, and unknown state.
- [ ] The system explains whether a value was entered, measured, or inferred.
- [ ] The helper mode identifies who is acting and records the participant’s consent.

## 7. Candidate and viewer-specific checks

- [ ] Every candidate has a non-3D structured summary.
- [ ] Every parameter has a label, unit, range, current value, source, and explanation.
- [ ] Viewer controls have accessible names and keyboard alternatives.
- [ ] The user can compare candidates without relying on color or rotation.
- [ ] Validation findings are grouped by status and severity with text explanations.
- [ ] Unassessed properties are prominent and not visually disguised as passes.
- [ ] Export confirmation identifies the exact candidate revision and limitations.

## 8. Testing protocol

Automated tests:

- [ ] axe-core or equivalent checks run on critical routes.
- [ ] Playwright keyboard flows cover onboarding, measurements, candidates, and export.
- [ ] Component tests cover focus, errors, dialogs, live regions, and reduced motion.
- [ ] CI prevents regressions in semantic labels and accessible names where practical.

Manual tests:

- [ ] Keyboard-only completion on desktop.
- [ ] Screen reader completion on desktop and mobile where supported.
- [ ] 200% zoom and narrow viewport.
- [ ] High contrast/forced colors.
- [ ] Reduced motion.
- [ ] Touch-only completion.
- [ ] Text-only/no-camera/no-audio completion.
- [ ] Moderated testing with disabled participants before public pilot.

## 9. Exit criteria

No critical blocker remains for core tasks. Any known limitation has an owner, a documented workaround, and a visible issue. Accessibility findings from disabled participants take priority over cosmetic preferences.

