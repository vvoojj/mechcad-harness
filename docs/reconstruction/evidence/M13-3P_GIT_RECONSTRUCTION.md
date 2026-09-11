# M13-3P Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_LIVE_VALIDATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M13_3P_GENERIC_M10_RIGID_BODY_CONSTITUENT_GROUP_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`f3ab0c7b16000bb14041c7f0fa56cef375441ceb` is the direct child of
`664ec3bf4ad7ef6d038f8e5bac483382dbda1125` and sole parent of
`ca294e045f53979cf6bc1d90404888501e50271f`. The delta is 18 files, 8,368
insertions, and 79 deletions: three documentation files, nine production
M10/application/provenance files, and six test files. New test function counts
are 90 grouped-body unit, 10 v1 golden, and 1 live FreeCAD test.

## Delivered Contract

`KinematicRigidBody` adds stable body IDs, reference CAD members, complete
member tuples, full-precision offsets, and semantic body hashes. Members belong
to exactly one body; reference offset is identity and other offsets must agree
under `rigid-transform-agreement@1.0`. V2 joints connect bodies, and topology is
a deterministic rooted forest with cycle/reachability validation.
`MultiJointKinematicsService` remains the sole FK engine and projects body poses
to members. `ExactConstituentPair` is neutral/unordered; same-body pairs are
excluded from generic external measurement but classified at the inventory
boundary. M10-3 reuses distinct-mesh exact measurement; M10-4 retains the
conservative `distance - relative` proof, with v2 computing both endpoint
bounds and `B_A + B_B`.

A post-review trust-boundary repair reconstructs and revalidates
`KinematicModelV2`, body hashes, and schema/evaluator/agreement versions before
FK/provider work. M10 v1 wire formats, hashes, FK, classification, and clearance
math are preserved.

## Evidence

Retained report: full suite `2,524 collected, 2,490 passed, 34 skipped, 0
failed` under Python 3.14.6, pytest 8.4.2, FreeCAD 1.1.3 via
`freecadcmd-subprocess`. Recorded live result hashes include discrete
`sha256:534a0efb...`, clear proof `sha256:f42fd5a8...`, and witness proof
`sha256:5dbf3fc9...`. The live fixture `R1,R2,A1,A2,B1,B2` exercised the
articulated `A2/B1` pair with trusted provider/backend provenance. Static gates
(compileall, diff check, dependency firewall, protected-region checks) passed.
`runtime.version` was null while backend provenance recorded FreeCAD 1.1.3.

## Limits

M10-3 remains discrete with `continuous_path_verified = False`; M10-4 proves
only the requested path, not configuration-space-wide clearance. No physical
authority, tolerance approval, FEA, materials, manufacturing, optimization, or
automatic synthesis is added. The plan remains unchecked; the completion report
is the acceptance record.

## Successor

`ca294e0` consumes the M13-3P v2 surface for the physical candidate/canonical
bridge without redefining it.

## Review Conclusion

Skeptical verification confirms the exact delta, 90/10/1 new-test counts,
2,524/2,490/34 full-suite record, live FreeCAD evidence, v1 preservation, and
the discrete/path-bounded motion limits.
