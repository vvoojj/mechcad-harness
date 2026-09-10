# M7D-2 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT_BUT_UNUSED
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

M7D-2 is a logical slice of shared commit
`8079c5764d377df3b182f8ffc72a306a186b57af`, parent `9ab9e48`, successor
`6c6f46c`. Its source is `src/mechcad_harness/yagi_el_sweep.py`; its tests are
three unit tests and one live integration test. M7D-1 reference implementation
is co-delivered and is not reclassified as M7D-2 source.

## Delivered Contract

The adapter validates EL-reference/layout binding, preserves layout,
reference, assembly, axis, and request identity through canonical hashes, marks
the fixture axis `REFERENCE_KINEMATIC_FIXTURE_ONLY`, and constructs a generic
discrete kinematic request. Generic sweep, transient-analysis, and FreeCAD
measurement services perform the actual evaluation.

The boundary is discrete only and has no canonical artifact or DesignState
mutation. It excludes mechanism selection, geometry embodiment, and continuous
verification.

## Tests And Evidence

The three unit tests pass in exact-tree reproduction. The FreeCAD-gated live
test is skipped when FreeCAD is unavailable. No target-era stdout, live result,
CI artifact, completion report, acceptance marker, tag, or Git note is retained.
The target audit records FreeCAD unavailable and the path as
`IMPLEMENTED_BUT_UNUSED`; the project description's completion wording is not
a dedicated M7D-2 acceptance result.

## Conformance And Deviations

The adapter receives no assembly object and therefore cannot independently
verify `source_assembly_hash`; generic source validation performs that check.
The request factory returns only the generic request, while richer adapter
reference identity is constructed separately. The live fixture proves generated
single-solid geometry only, not imported components, multi-shape STEP, or
production orchestration.

## Successor

`6c6f46c` preserves M7D-2 and adds source-bound CAD/imported-component and
production kinematic paths. Later M9 live evidence is not M7D-2 acceptance.

## Review Conclusion

Skeptical review confirms the shared boundary, four tests, discrete/runtime-
gated scope, explicit fixture-only provenance, and absent retained acceptance.
