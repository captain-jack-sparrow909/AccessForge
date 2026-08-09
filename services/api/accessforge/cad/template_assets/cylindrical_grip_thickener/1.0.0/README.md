# Cylindrical grip thickener · template 1.0.0

Status: `reviewed_repository_only` — provisional metadata for deterministic
software development and synthetic fixtures. It is not a physical-use approval,
fit guarantee, safety certification, ergonomic claim, or medical-device claim.

## Intended narrow use

This template describes a removable split sleeve around a low-energy pen,
stylus, brush, or similar cylindrical handheld object at room temperature. Do
not use it for safety-critical controls, sustained skin contact, unknown loads,
high-cycle use, hot/wet/chemical environments, food contact, medical functions,
or any context outside the confirmed project scope.

## Parameters

All values are canonical millimetres. The compiler must reject missing or
out-of-range values and combinations with insufficient wall thickness.

| Parameter | Range | Default | Meaning |
| --- | ---: | ---: | --- |
| `inner_diameter` | 4–22 | 10 | Measured target-object diameter. |
| `outer_diameter` | 16–45 | 28 | Overall grip diameter. |
| `grip_length` | 35–160 | 100 | Axial sleeve length. |
| `slit_width` | 0.8–5 | 2.4 | Nominal longitudinal split width. |
| `edge_radius` | 0.5–2.5 | 1 | Nominal geometric edge rounding. |

`outer_diameter` must leave the policy's minimum wall thickness after the
inner opening is applied. The template must report invalid combinations rather
than silently changing either diameter.

## Print and inspection guidance

Choose and record an orientation that avoids an unsupported long split where
possible. Review generated overhang/bridge findings for the specific process.
Before controlled non-human fixture evaluation, inspect the inner opening,
split, end edges, layer adhesion, and measured dimensions. The split does not
prove a particular material can flex, retain the object, or remain comfortable.

## Known limitations

This template does not test grip comfort, dexterity benefit, hygiene, skin
compatibility, retention force, fatigue, material behavior, or fit. A rounded
edge parameter is not a complete sharp-edge or skin-contact assessment. Any
changed parameter, material/process profile, requirement revision, or
risk-relevant context requires a new immutable DesignSpec and candidate.
