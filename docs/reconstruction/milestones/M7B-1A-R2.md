# M7B-1A-R2 - Azimuth Mount Interface Authority

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: CO_DELIVERED_IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

M7B-1A-R2 is `19f77a30ef42040d5f07688ab4235a25daaba7f0`, the direct child of
M6B-4C `4468a621dfdf0662acf74501e13b5b182920cf13` and direct parent of
`7c7352a57632d6202a25351761f5cfe0e15adc5b`. The full commit changes 42 files
with 2,629 insertions and 13 deletions. It co-delivers broader M7A CAD,
assembly, artifact, and exact-analysis infrastructure.

## Attributable M7B Scope

The M7B slice changes 11 files with 567 insertions and 4 deletions. It adds
typed azimuth drive mounting-interface authority: threaded and through holes,
required mating holes, mount-point IDs, coordinate/frame semantics, central
keepout/opening, and radial-clearance semantics. It wires supported keys,
canonical values, typed answers, anchors, request satisfaction, and resolution
application.

It also adds a deterministic fixture-only motor-mount plate model/compiler,
hash, measurements, readiness check, and missing-input report. It does not
provide deterministic synthesis, canonical persisted plate state, real
manufacturer hardware, structural validation, or manufacturing approval.

## Tests And Execution Evidence

The attributable M7B test suite contains 24 functions: 6 mount-plate, 5
authority, 12 semantic, and 1 FreeCAD integration test. Git adds all 24
functions; the
curated R2-only semantic subset is 17 functions (5 authority and 12 semantic).
The focused M7B reproduction passed all 24. The full candidate reproduction
yielded `383 passed, 31 skipped,
1 failed`, with the inherited py_gearworks availability assertion causing the
failure.

The FreeCAD test uses synthetic fixture data and explicit
`M7B1_TEST_FIXTURE_ONLY` provenance. It is not real manufacturer hardware
evidence. No generated artifact, workspace result, completion report, audit,
acceptance marker, tag, or Git note is retained.

## Material Deviations

- The authority carrier stores `mount_points` as `tuple[dict, ...]`, while
  `MountPointSpec` is typed; validation checks uniqueness but does not carry the
  richer typed semantics end to end.
- The integration guard checks package importability rather than
  `discover_freecad().available` and hard-codes the FreeCAD executable path.
- Full azimuth request materialization through the resolution materializer and
  application service is not tested end to end.
- No dedicated M7B specification, plan, or acceptance record exists at this
  boundary.

## Successor Relationship

`7c7352a` adds deterministic synthesis: design-requirements authority,
stock-thickness policy, envelope/ligament calculation, draft proposals,
persisted `azimuth_mount_plates`, ownership, and synthesis tests. It reuses
this interface foundation; synthesis is successor scope.

## Reconstruction Conclusion

M7B-1A-R2 is a proven co-delivered interface-authority implementation with a
synthetic fixture-only CAD path, partial typed coverage, and no retained formal
acceptance evidence.

See [detailed Git evidence](../evidence/M7B-1A-R2_GIT_RECONSTRUCTION.md).
