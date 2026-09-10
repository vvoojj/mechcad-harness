# M7D-1 Historical Reconstruction

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

M7D-1 is attributed to the shared `8079c5764d377df3b182f8ffc72a306a186b57af`
commit between `9ab9e48` and `6c6f46c`. Its five files are the M7D-1 design,
plan, `yagi_el_reference.py`, and two unit-test modules; the curated addition is
539 lines. M7D-2 is a separate logical slice in the same commit.

## Delivered Contract

`YagiELKinematicReference` is frozen and strict, fixes EL axis height to
`(180.0, 300.0)`, leaves `selected_axis_height_mm` unset, and computes a
deterministic SHA-256 identity. Its request helper accepts explicit assembly
identity, axis, angle order, and moving/stationary instance IDs while preserving
caller ordering. Generic sweep services are reused and unchanged.

The contract excludes mechanism/geometry embodiment, motor sizing, materials,
loads, FEA, state mutation, and continuous verification. No production caller
exists in the target tree.

## Tests And Evidence

`test_m7d1_el_reference.py` and `test_m7d1_el_sweep_reference.py` contain six
tests, all passing in exact-tree reproduction. A broader generic kinematic
scope yields 19 passing tests. No target-era output, live result, generated
artifact, CI transcript, or dedicated M7D-1 acceptance record is retained.

The target's project description and integration audit are same-commit
documentation; the audit says FreeCAD was unavailable and the path was
`IMPLEMENTED_BUT_UNUSED`. They are not a live acceptance transcript.

## Conformance And Deviations

The plan's simplified helper omits explicit source assembly ID/hash, while the
implementation requires them. Assembly identity is separately supplied
executable provenance, not derived from layout. The helper invokes reference
factories for validation but does not apply reference transforms. The fixed
tuple is exact rather than a general finite/ascending validator.

## Successor

M7D-2 consumes this reference boundary. Direct successor `6c6f46c` leaves the
source and tests unchanged while adding M8C imported-component and production
kinematic capabilities. Later M9 verification is successor evidence only.

## Review Conclusion

Skeptical review confirms the shared boundary, five-file/539-line attribution,
six tests, reference-only scope, absent production caller, and lack of retained
acceptance evidence.
