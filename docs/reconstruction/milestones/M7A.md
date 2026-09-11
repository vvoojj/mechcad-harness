# M7A - Generic CAD / Assembly / Exact Geometry Foundation

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_LIVE_ACCEPTANCE
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: NO_DEDICATED_SPEC_TRACEABILITY_MISSING
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: REPORTED_COMPLETE_NO_DEDICATED_ACCEPTANCE_GATE
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

M7A source is co-delivered in `19f77a30ef42040d5f07688ab4235a25daaba7f0`,
shared with M7B-1A-R2, whose predecessor is M6B-4C
`4468a621dfdf0662acf74501e13b5b182920cf13` and whose successor is M7B-1B
`7c7352a57632d6202a25351761f5cfe0e15adc5b`. M7A live acceptance artifact
trees are committed later in `8079c5764d377df3b182f8ffc72a306a186b57af`.

M7A has no dedicated spec, plan, or acceptance gate; it is reconstructed from
committed source, committed live acceptance artifacts, and normative project/
architecture statements.

## Historical Role And Sub-Layers

- **M7A-1 — FreeCAD backend foundation:** deterministic FreeCAD execution and
  derived CAD generation in `backends/freecad.py`/`freecad_assembly.py`.
- **M7A-2A — Typed CAD operations:** generic base plates, holes, rectangular
  pockets, and slots via `cad_program.py`/`cad_manifest.py`.
- **M7A-2B — Assembly foundation:** rigid component placement,
  `CadAssemblyProgram`, `CadRigidTransform`, deterministic assembly identity and
  ordering via `cad_assembly.py`/`cad_assembly_manifest.py`.
- **M7A-2C — Exact interference/clearance analysis:** exact FreeCAD
  `shape.common(other).Volume` and `shape.distToShape(other)[0]` with generic
  interference/touching/positive-clearance classification via
  `cad_analysis.py`/`analysis_service.py`.

The CAD operation layer is generic and contains no domain-specific Yagi logic;
the domain-specific Yagi work belongs to M7B.

## Tests And Live Acceptance Evidence

The M7A source boundary adds 62 test functions across 14 files (10 unit files
and 4 live integration files: `test_cad_program_live.py`,
`test_cad_analysis_live.py`, `test_cad_assembly_live.py`,
`test_freecad_backend_live.py`). No historical pass transcript is retained.

Committed live acceptance artifacts prove M7A-2C real FreeCAD 1.1.3 measurement:
the `PRJ-M7A2C-ACCEPTANCE-FINAL` analyses record interfering interference
`4573.805328941535 mm3` (fail), separated `20.0 mm` clearance with zero
interference (pass), and touching `0.0` interference/`0.0` clearance (pass),
under analyzer `mechcad-freecad-clearance@1.0`. `PRJ-M7A1-ACCEPTANCE`,
`PRJ-M7A2A-ACCEPTANCE`, and `PRJ-M7A2B-ACCEPTANCE` retain generated plate and
generated-part rigid assembly FCStd/STEP artifacts with artifact metadata.
Imported-component assembly is **not** an M7A capability; it is introduced later
at M8C-2 `6c6f46c`.

These prove that a real FreeCAD backend, generic typed CAD, rigid assembly
realization, and exact interference/clearance measurement existed at this
boundary. This is the historical origin of the exact
interference/clearance primitive that later M8C/M9 reuse.

## Material Deviations

- No M7A spec, plan, or dedicated acceptance record exists. The architecture
  reconciliation records this as `TRACEABILITY_MISSING` (R-031/R-034) while
  classifying M7A as `REQUIRED_CURRENT`.
- M7A has no dedicated feature commit; its source shares `19f77a3` with
  M7B-1A-R2 and its acceptance artifacts land in a later commit (`8079c57`).

## Successor Relationship

M7B-1B `7c7352a` adds domain-specific azimuth synthesis on this generic
foundation. Later M8C connects generic CAD to production and M9 live-verifies
the trusted-import/measurement chain.

## Reconstruction Conclusion

M7A is a proven generic CAD/assembly/exact-geometry implementation with real
committed FreeCAD acceptance artifacts, no dedicated specification, and a
`TRACEABILITY_MISSING` normative status.

See [detailed Git evidence](../evidence/M7A_GIT_RECONSTRUCTION.md).
