# M8C - CAD, Imported Assembly, And Production Kinematics

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_IMPLEMENTATION
IMPLEMENTATION_STATUS: ARCHITECTURALLY_CLOSED_RUNTIME_GATED
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_AUDIT_SUMMARY
ACCEPTANCE_STATUS: RUNTIME_GATED
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

M8C is bundled in `6c6f46c06fb0ba624639832c1f7c224d3c34d39b`, the direct child
of `8079c5764d377df3b182f8ffc72a306a186b57af` and direct parent of
`a67cee375e793a573fe4c77fceddf9cea76d9dc0`. It changes 19 files with 3,483
insertions and 10 deletions.

## Logical Layers

- M8C-1 compiles source-bound `MountingPlateDesignSpec` to deterministic
  `CadPartProgram` output.
- M8C-2 resolves trusted STEP artifacts to `ImportedCadComponent` and builds
  mixed generated/imported `CadAssemblyProgram` values.
- M8C-3 connects `ProductionApplication` to a discrete kinematic sweep through
  transient exact-measurement services.

The three specs are present, but M8C-1 has no separate plan. The commit adds no
M8C workspace artifacts; tests use temporary synthetic fixtures, including a
header-only STEP and synthetic imported metadata.

## Tests And Evidence

The bundle adds 81 test functions: M8C-1 35, M8C-2 35, and M8C-3 11. The
retained M8C audit reports `632 passed, 51 skipped`; the M8C-3 plan contains a
conflicting earlier `629 passed, 51 skipped` report. Skips are FreeCAD-gated.
No raw logs, durable M8C kinematic result, provider-provenance artifact, or
live FreeCAD execution record is retained.

This supports an architecturally closed, runtime-gated classification, not
independent live acceptance.

## Material Deviations

- Imported components can be routed through the generated-part branch before
  `Part.insert`; M9-2 later adds explicit imported routing and object cleanup.
- The transient provider builds generated-part paths only; mixed imported sweeps
  fail until M9-3 adds trusted imported-artifact resolution.
- Production assembly accepts caller-authored provenance unless explicit
  imported-component resolution is used.
- Caller-preaccepted DesignSpec, separate compilation provenance, runtime-only
  run identity, absent backend/provider provenance, and no live FreeCAD run are
  accepted limitations at this boundary.
- The candidate diff contains trailing whitespace.

## Successor Relationship

`a67cee3` preserves the M8C records as a runtime-gated baseline. M9 adds real
STEP production, live FreeCAD mixed assembly/reload, exact measurements,
durable execution provenance, and the imported-routing/transient fixes. Those
successors upgrade runtime proof and do not retroactively establish M8C live
acceptance.

## Reconstruction Conclusion

M8C is a proven three-layer CAD/assembly/kinematics implementation with retained
audit summary, runtime-gated FreeCAD behavior, and successor-identified mixed
import limitations.

See [detailed Git evidence](../evidence/M8C_GIT_RECONSTRUCTION.md).
