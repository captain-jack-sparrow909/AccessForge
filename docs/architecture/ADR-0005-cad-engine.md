# ADR-0005: Deterministic parametric CAD engine

Status: proposed  
Date: 2026-08-08

## Context

AccessForge needs personalized geometry while preserving reproducibility and safety boundaries. A language model can describe intent but should not emit arbitrary geometry or code. The project needs editable CAD artifacts, preview meshes, and template-level constraints.

## Decision

Use reviewed, versioned CadQuery templates and a typed DesignSpec. The compiler converts canonical-unit parameters into geometry in a sandboxed worker. `trimesh` and dedicated validators inspect generated meshes and artifact consistency. Export STEP, STL, GLB, machine-readable DesignSpec, validation report, and provenance manifest.

The MVP executes only repository-reviewed, signed templates. Community templates are manifest-only until a restricted declarative format or isolated review pipeline exists. Uploaded/community Python is never executed by hosted production.

## Alternatives considered

- LLM-generated OpenSCAD/CAD code: flexible but difficult to bound, validate, reproduce, or secure.
- Blender Geometry Nodes: powerful, but less direct for precise parametric mechanical parts and backend headless operation.
- OpenSCAD-only templates: accessible and useful, but CadQuery provides a stronger Python API for typed domain integration and future geometry logic.
- Fully generic mesh generation: poor editability and weaker parameter provenance.

## Consequences

Positive:

- deterministic inputs and versioned template contracts
- editable STEP output
- clear safety review boundary at the template level
- testable geometry invariants

Costs:

- OCCT/CAD dependencies make Docker images heavier
- template maintainers need CAD and testing skills
- physical validation remains necessary and cannot be inferred from geometry alone

## Guardrails

- canonical SI units enter the compiler
- no silent parameter clamping
- complexity, CPU, memory, wall-time, and output-size limits
- no network in compiler sandbox
- record every repair, transform, version, seed, and artifact hash
- failed critical validation blocks approval/export

