# M11-5 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_EVIDENCE
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M11_5_DURABLE_STRUCTURAL_EVIDENCE_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`07950cd1b172d2e110d1fbc1197a53bcb47f67e1` is the direct child of
`682300b586b5e4f099d6da615a72405ba51b32e9` and direct parent of
`4d436cfe53b390a94490a067366c7ae3458bb045`. The delta is 36 files, 8,686
insertions, and 316 deletions. M11-6's seven-file documentation delta must not
be attributed to M11-5.

## Delivered Capability

The candidate adds structural Evidence models/publisher/verifier,
repeatability, convergence services, ProductionApplication APIs, C3D10 mesh
normalization, and same-mesh MSH-to-INP lowering. Evidence binding covers
project/source revision/state hash, definition/request, geometry/mesh/solver
artifacts, typed results, criteria, material/analytical authority, and trusted
provenance. Artifact integrity failures remain distinct from engineering
`NOT_EVALUABLE`.

Repeatability compares semantic summaries only, excluding raw bytes, mesh
numbering, and solver ordering. The declared policy hash is
`sha256:916a7d312708b4676dc20f9107d8f49f4b39fdd364bc6ccd829c40660e95517c`.
The recorded convergence study has levels 10.0/7.5/5.0 mm, displacement
magnitudes `2.261627083333334`, `2.2642747222222224`,
`2.267595845655101`, and relative changes `0.0011693099` and `0.0014646011`.

## Retained Execution Evidence

Committed M11-5 reporting records 520 focused passes, 6 live passes, one
convergence pass, 14 M11-3/4/5 regressions, broader `154 passed, 9 skipped`,
and full `1,371 passed, 34 skipped`. CalculiX 2.22 executed without a skip.
The reports were not rerun during reconstruction. No M11-5 Evidence JSON, raw
MSH/INP/FRD/DAT/LOG tree, or `PRJ-M11*` workspace is committed.

## Limits And Successor

Fresh verification uses fresh stores/instances, not a separately spawned OS
process. Convergence is only free-end transverse displacement magnitude, not
global stress, adaptive refinement, generic mesh independence, or safety.
The plan remains unchecked. M11-6 later adds system acceptance documentation;
it does not supply M11-5 implementation.

## Review Conclusion

Skeptical review confirms the 36-file implementation boundary, durable Evidence
binding, retained live/repeatability/convergence reports, distinct-mesh work,
and bounded limitations.
