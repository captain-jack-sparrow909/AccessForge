# AccessForge built-in template assets

This directory contains the only template metadata intended to be trusted by the
Phase 4 registry. Each version directory is an immutable, repository-reviewed
release record containing:

- `manifest.yaml` — JSON-formatted YAML with the typed public contract.
- `preview-fixture.json` — synthetic, deterministic input for previews and
  golden geometry tests.
- `README.md` — plain-language print guidance and known limitations.

The `reviewed_repository_only` status means that a release is bundled with this
repository and may be resolved only by an allowlisted registry. It does **not**
mean that the template is approved for real-world use, physical output,
professional review, or safety certification. The Phase 0 risk taxonomy and
future deterministic risk/validation gates remain mandatory.

All parameter values in these manifests and fixtures are canonical millimetres.
The compiler must reject missing, non-finite, or out-of-range values without
silently clamping them. It must not execute code supplied by a manifest, user,
or community contributor. A template ID and version must resolve to a bundled
directory exactly; arbitrary paths, module names, archives, and uploaded
templates are not valid inputs.

The first three families are deliberately narrow:

1. `pull_tab_extender`
2. `cylindrical_grip_thickener`
3. `handle_sleeve`

Their ranges are engineering inputs for deterministic software tests, not
evidence of fit, material performance, durability, accessibility benefit, or
safety. Do not represent a generated artifact as tested or safe merely because
it conforms to this metadata.
