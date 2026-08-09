# Handle sleeve · template 1.0.0

Status: `reviewed_repository_only` — provisional metadata for deterministic
software development and synthetic fixtures. It is not a physical-use approval,
fit guarantee, safety certification, ergonomic claim, or medical-device claim.

## Intended narrow use

This template describes a removable split sleeve around a non-safety-critical
cabinet or drawer handle for an occasional, low-energy pull at room temperature.
It must never be selected for a lock, child-safety feature, emergency exit,
appliance safety control, vehicle, mobility aid, brake, load-bearing function,
or any unknown/high-risk context.

## Parameters

All values are canonical millimetres. The compiler must reject missing or
out-of-range values and combinations with insufficient wall thickness.

| Parameter | Range | Default | Meaning |
| --- | ---: | ---: | --- |
| `handle_diameter` | 6–35 | 16 | Measured target-handle diameter. |
| `fit_clearance` | 0.3–2 | 0.8 | Nominal fit allowance; not a fit guarantee. |
| `outer_diameter` | 18–55 | 32 | Overall sleeve diameter. |
| `sleeve_length` | 35–220 | 110 | Axial sleeve length. |
| `slit_width` | 0.8–6 | 2.8 | Nominal longitudinal split width. |
| `edge_radius` | 0.5–3 | 1.2 | Nominal geometric edge rounding. |

`outer_diameter` must leave the policy's minimum wall thickness after the
recorded handle diameter and clearance are applied. The template must report an
invalid combination instead of silently changing it.

## Print and inspection guidance

Choose and record an orientation that reduces unsupported longitudinal features
without changing the documented dimensions. Review generated overhang, bridge,
and build-volume findings for the selected process. Before controlled non-human
fixture evaluation, inspect the inner opening, split, end edges, layer adhesion,
handle clearance, and measured dimensions.

## Known limitations

This template does not test retention, pull force, fatigue, comfort, skin
compatibility, mounting integrity, material behavior, fit, or accessibility
benefit. A rounded edge parameter is not a complete sharp-edge or injury
assessment. Any changed parameter, material/process profile, requirement
revision, or risk-relevant context requires a new immutable DesignSpec and
candidate.
