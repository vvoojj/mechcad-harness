# M7B-2B/R2/R3/R4 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_IMPLEMENTATION
IMPLEMENTATION_STATUS: PRELIMINARY
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Labels

`3f7bbc76f6031d1374b0b476a4d58da1dce37dfd` is the direct child of
`30b99eb02cf2fbb627fb59378e34372dbd7adfc9` and direct parent of
`9ab9e48b8bc54202d5fddd5edc85e7f8c7c3b903`. The delta is 18 files, 1,430
insertions, and 12 deletions. No dedicated M7B specification, plan, audit,
completion, or acceptance record exists at this boundary.

The compact source/test labels identify a single bundled delivery of M7B-2B,
M7B-2B-R2, M7B-2B-R3, and M7B-2B-R4. It is not evidence for later M7B-2C or
M7C1 collision/kinematic work.

## Delivered Scope

`yagi_carrier.py` consumes exact Yagi authority and produces deterministic
carrier requirements, nominal antenna positions, representative envelope
collision checks, hashes, and draft proposals. `yagi_clamp_slider.py` derives
slot width/length from slider diameter, radial clearance, and travel without
clipping infeasible geometry. `yagi_sliding_interface.py` selects native
extrusion/T-slot architecture with preliminary `2040` and preferred `4040`
guidance.

`yagi_carrier_packaging.py` provides only a preliminary `40 x 500 x 40 mm`
envelope and four-instance reference assembly. Generic `ThroughSlotOperation`
is validated, hashed, manifested, compiled, and probed. `/yagi_carriers/*`
ownership and canonical carrier storage are added.

`compile_preliminary_yagi_carrier()` remains fail-closed with
`M7B2B_CAD_OPERATION_CAPABILITY_REQUIRED`. There is no final extrusion/T-slot
geometry, clamp hardware, through-slot carrier geometry, structural validation,
manufacturing accuracy, or accepted final positioning.

## Tests And Reproduction Accounting

The candidate-focused exact-tree scope yields 59 collected cases: `57 passed, 2
skipped`. The skips are `test_m7b2br4_carrier_live.py` and
`test_through_slot_freecad_live.py`. Adding parent M7B-2A authority tests yields
67 passing unit cases. Full exact-tree reproduction is `466 passed, 33 skipped,
1 failed` out of 500; the failure is the inherited py_gearworks-unavailable
assertion while py_gearworks 0.0.18 is installed.

FreeCAD discovery was unavailable, so live FreeCAD behavior was not reproduced.
No historical stdout, generated artifact, workspace result, CI result,
completion report, acceptance marker, tag, or Git note is retained.

## Successor

The chain is `30b99eb -> 3f7bbc7 -> 9ab9e48 -> 8079c57`. `9ab9e48` adds
M7B-2C collision-layout synthesis, generic transient measurement, and M7C1
kinematic sweep. Later `8079c57` adds production/artifact work and repairs
successor ownership gaps. Those commits do not establish acceptance for this
preliminary bundle.

## Review Conclusion

Skeptical review confirms the four bundled labels, exact 18-file delta, 59/57/2
focused accounting, 67 combined unit cases, 500-case full snapshot, fail-closed
carrier compilation, unavailable FreeCAD reproduction, and absent acceptance
evidence.
