# M10 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_SYSTEM_IMPLEMENTATION_AND_ACCEPTANCE
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_HISTORICAL_OBSERVATION
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M10_FULLY_CLOSED_LIVE_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`89b1d758f6668e84cd86d7a61bf28b3974dc1c24` is the direct child of
`a67cee375e793a573fe4c77fceddf9cea76d9dc0` and direct parent of
`682300b586b5e4f099d6da615a72405ba51b32e9`. The delta is 45 files, 11,749
insertions, and 32 deletions. It bundles M10-1 through M10-5, four specs, two
plans, completion reports, a system acceptance audit, production source, and
tests.

## Delivered Contract

M10-1 supplies conservative single-axis continuous proof with chord/radial
motion bounds and three fail-closed outcomes. M10-2 supplies deterministic
forward kinematics over a rooted acyclic revolute-joint forest, transformed
assemblies, and separate identity hashes. M10-3 supplies exact discrete
multi-joint collision sweeps through FreeCAD `common().Volume` and
`distToShape()`, ordered classifications, and provenance. M10-4 supplies
hierarchical telescoping bounds and exact checks along one explicit
piecewise-linear raw joint-space path. M10-5 ties these through live acceptance,
durable Evidence reload, provenance, immutability, and regression checks.

## Test And Runtime Evidence

Retained M10-specific accounting is 34 + 53 + 75 + 18 + 1 for M10-1 through
M10-5. Runtime-configured acceptance reports `871 passed, 25 skipped`; the
retained unconfigured report records `844 passed, 51 skipped` because optional
runtime paths were unavailable. FreeCAD 1.1.3, backend
`mechcad-freecad@2.1`, provider `mechcad-freecad-transient@1.0`, and
`freecadcmd-subprocess` are identified in the retained reports.

M10-4 recorded clear, requested-clearance-witness, and budget-limited results;
M10-5 passed the integrated capstone and durable reload. The M10-1 report's
named `scripts/m10_1_evidence_capture.py` is absent from the exact tree, so
that portion is report-backed rather than independently rerunnable from Git.

## Historical Observation: M10-4 Partition Validation

`MultiJointContinuousPathRequest.validate_request()` checks overlap but not
duplicate, unknown, or complete assembly membership. The proof service does not
invoke full request/assembly partition validation at execute time. Duplicate or
omitted IDs, and unknown IDs with a permissive low-level measurement stub, can
reach `VERIFIED_CLEAR`; a real FreeCAD provider fails on unknown instance lookup.
The M10-4 plan's named
`tests/unit/test_m10_4_regressions.py` is also absent; coverage is distributed
elsewhere. The M10 system audit overstates this validation coverage. These are
historical observations, not source patches.

## Limits And Successor

M10-3 remains discrete with `continuous_path_verified=False`; M10-4 proves only
one explicit piecewise-linear path, not arbitrary configuration-space regions or
general trajectories. M11 begins at `682300b` and leaves M10-specific modules,
tests, audits, and specs unchanged; it modifies shared application/backend/
artifact/model files but does not repair the partition gap. Later structural and candidate
milestones are successors, not M10 evidence.

## Review Conclusion

Skeptical review confirms the 45-file boundary, five-layer scope, retained live
acceptance counts, missing evidence-script/planned-regression observations,
M10-4 partition gap, and explicit motion-proof limits.
