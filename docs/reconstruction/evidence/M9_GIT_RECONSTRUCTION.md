# M9 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: SYSTEM_ACCEPTANCE_IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M9_FULLY_CLOSED_LIVE_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`a67cee375e793a573fe4c77fceddf9cea76d9dc0` is the direct child of
`6c6f46c06fb0ba624639832c1f7c224d3c34d39b` and direct parent of
`89b1d758f6668e84cd86d7a61bf28b3974dc1c24`. The delta is 19 files, 2,630
insertions, and 36 deletions. Four M9 specs, one system acceptance audit, six
production changes, and M9 test changes are included. No M9 workspace artifact
is committed.

## Delivered Closure

M9-1 closes real FreeCAD runtime compilation/persistence/reload and backend
identity. M9-2 runs `mechcad-build-spur-gear-cad@1.0` through py_gearworks and
build123d, stores and byte-verifies a real STEP, and resolves it through trusted
`ArtifactStore` provenance. M9-3 realizes and reloads a mixed generated/imported
assembly and performs exact transient `common().Volume` / `distToShape()`
measurements. M9-4 stores provider, backend, runtime, request/result, and
source-assembly provenance in Evidence.

The `ImportedCadComponent` schema is unchanged. Source immutability,
deterministic identities, and `continuous_sweep_verified=False` remain.

## Live Acceptance Evidence

The retained M9 system audit and test records report FreeCAD 1.1.3,
`mechcad-freecad@2.1`, `freecadcmd-subprocess`, py_gearworks 0.0.18, and
build123d 0.11.1. The audit-recorded STEP is 443,209 bytes,
`sha256:ee7dc56408763b727e592ce466fab8a42bbaa50a74045d1fb35c9c940b41d555`.
The reloaded two-solid mixed assembly preserved placement `[20.0, 0.0, 5.0]`.

At 0/90/180/270 degrees, recorded interference/clearance values are
`0/6`, `0/26`, `0/14.922814`, and `545.434337/0`. Repeated sweeps matched
within floating-point tolerance. No public per-angle artifacts were created.

## Tests And Correction

Exact M9 tests are 7 M9-1, 7 M9-2, 1 M9-3, and 10 M9-4, totaling 25. The
retained audit reports 25 passed M9 tests and `689 passed, 25 skipped` for the
full suite. Its M9-2 row says 8 tests, which is a documentation error; the exact
M9-2 file and spec each contain 7. Candidate rerun evidence also reports 25 M9
passes and the same full-suite count.

No raw logs are retained, but the committed audit, specs, and test records are
durable acceptance evidence. M9 workspace artifacts were temporary, not
committed. Assembly/request/result hashes in the records are historical
run-specific values because artifact IDs are UUID-based, not replay constants.
The STEP hash is retained audit evidence and was not independently recomputable
from Git because the binary was not committed.

## Remaining Limits And Successor

M9 does not prove continuous motion, multi-axis/configuration-space safety, FEA,
materials, manufacturing, optimization, or automatic selection. DesignSpec is
caller-preaccepted; compilation provenance is not folded transitively into
assembly identity; `run_id` is correlation scope. M10-3 remains discrete with
`continuous_path_verified = False`, and M10-4 proves only one explicit
piecewise-linear joint-space path, not arbitrary configuration-space regions or
general trajectories. M10 directly follows and reuses these foundations for
continuous and multi-joint analysis.

## Review Conclusion

Skeptical review confirms the four-layer live closure, exact 19-file delta,
25-test split, real artifact/hash/measurement evidence, M9-2 count correction,
run-specific hash qualification, and retained limitations.
