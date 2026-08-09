# Pull-tab extender · template 1.0.0

Status: `reviewed_repository_only` — provisional metadata for deterministic
software development and synthetic fixtures. It is not a physical-use approval,
fit guarantee, safety certification, or medical-device claim.

## Intended narrow use

This template describes a passive extension for a small zipper or pull tab used
for an occasional, low-energy pull at room temperature. It is not appropriate
when the attachment affects a mobility aid, vehicle, brake, lock, safety feature,
emergency access, medical use, load-bearing function, or any unknown/high-risk
context.

## Parameters

All values are canonical millimetres. The compiler must reject a missing or
out-of-range value instead of changing it automatically.

| Parameter | Range | Default | Meaning |
| --- | ---: | ---: | --- |
| `attachment_slot_width` | 4–24 | 12 | Measured width of the existing pull-tab opening. |
| `attachment_slot_height` | 3–16 | 7 | Measured height of the existing pull-tab opening. |
| `attachment_clearance` | 0.3–2 | 0.8 | Extra fit allowance; not a fit guarantee. |
| `pull_loop_outer_width` | 20–60 | 36 | Overall loop width. |
| `pull_loop_outer_height` | 16–60 | 28 | Overall loop height. |
| `body_thickness` | 2.4–5 | 3.2 | Nominal body thickness. |
| `edge_radius` | 0.6–3 | 1.2 | Nominal geometric edge rounding. |

The template must additionally reject combinations that leave insufficient
material around the attachment opening. It must report, rather than silently
correct, any combination that conflicts with the template policy.

## Print and inspection guidance

Choose and record an orientation that keeps the loop stable while reducing
unsupported internal openings. Review the generated manufacturing findings for
your process; there is no universal no-support orientation. Before controlled
non-human fixture evaluation, inspect for cracks, incomplete layers, rough
edges, dimensional drift, and attachment interference.

## Known limitations

This geometry metadata does not test pull strength, fatigue, material behavior,
comfort, pinch hazards, attachment retention, or fit. A rounded edge parameter
does not complete a sharp-edge or injury assessment. Changes to any parameter,
material/process profile, requirement revision, or risk-relevant context need a
new immutable DesignSpec and candidate.
