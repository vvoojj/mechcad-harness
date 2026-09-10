# M7B-2B/R2/R3/R4 - Preliminary Yagi Carrier CAD

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_IMPLEMENTATION
IMPLEMENTATION_STATUS: PRELIMINARY
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

This bundled boundary is `3f7bbc76f6031d1374b0b476a4d58da1dce37dfd`, the
direct child of M7B-2A `30b99eb02cf2fbb627fb59378e34372dbd7adfc9` and direct
parent of `9ab9e48b8bc54202d5fddd5edc85e7f8c7c3b903`. It changes 18 files with
1,430 insertions and 12 deletions.

Source and test names support four bundled labels: M7B-2B carrier synthesis,
M7B-2B-R2 clamp/slider boundary, M7B-2B-R3 sliding-interface architecture,
and M7B-2B-R4 preliminary packaging/closure.

## Historical Role And Result

The candidate consumes typed Yagi authority and adds carrier synthesis,
clamp/slider classification, native extrusion/T-slot guidance, preliminary
packaging, generic `ThroughSlotOperation`, manifests, FreeCAD generation,
verification probes, assembly-solid-count validation, `/yagi_carriers/*`
ownership, and `DesignState.yagi_carriers`.

Carrier synthesis requires matching authority revision/hash and computes
deterministic length, nominal antenna positions, representative envelope
collision checks, results, and proposals. R4 compiles only a preliminary
`40 x 500 x 40 mm` box and four-instance reference assembly. Actual carrier
compilation fails closed with `M7B2B_CAD_OPERATION_CAPABILITY_REQUIRED`.

Exact extrusion profiles, T-slot geometry, T-nut/clamp hardware, manufacturing
geometry, structural verification, final positions, and acceptance remain
unresolved.

## Tests And Execution Evidence

The candidate-focused scope contains 59 collected cases: 57 passed and 2
skipped. The two skipped cases are the carrier and through-slot FreeCAD live
tests. Including the parent M7B-2A authority tests gives 67 passing unit cases.
The full exact-tree reproduction contains 500 cases: `466 passed, 33 skipped,
1 failed`, with the inherited py_gearworks availability assertion causing the
failure.

FreeCAD discovery was unavailable for this reproduction, so no live FreeCAD
result was established. No generated Yagi FCStd/STEP artifact, workspace
result, completion report, audit, acceptance marker, tag, or Git note is
retained.

## Reconstruction Conclusion

M7B-2B/R2/R3/R4 is a proven preliminary carrier-CAD implementation bundle with
generic operation plumbing, fail-closed final compilation, and no retained
formal acceptance evidence.

See [detailed Git evidence](../evidence/M7B-2B-R2-R4_GIT_RECONSTRUCTION.md).
