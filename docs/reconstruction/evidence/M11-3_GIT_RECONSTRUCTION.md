# M11-3 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Delivered Foundation

M11-3 is a logical slice of `682300b586b5e4f099d6da615a72405ba51b32e9`, after
M10 `89b1d75`. It is co-delivered with M11-2/4 and is not represented by a
standalone commit. M11-5 begins at `07950cd1b172d2e110d1fbc1197a53bcb47f67e1`.

The source provides trusted FreeCAD source geometry, single-solid admission,
semantic region resolution, Gmsh C3D10 meshing, deterministic CalculiX deck
lowering, constraint preflight, solver execution, and trusted runtime
provenance/raw artifacts. It remains source-bound single-body linear-static.

## Evidence Accounting

Retained reports cite full results of `1,021 passed, 34 skipped` and later
`1,189 passed, 34 skipped`; the focused report cites 151 passes. Exact
candidate-scoped recount finds 173 collected cases and reproduced 172 passes
and 1 failure. These are not one interchangeable historical run, and no raw
transcript is retained.

The runtime proof identifies FreeCAD 1.1.3, Gmsh 4.15.0, and CalculiX 2.22.
No durable M11-3 Evidence or mesh-convergence result exists at this boundary.

## Limits

No assemblies, contact, nonlinear/fatigue/dynamic/thermal analysis,
tolerances, optimization, manufacturing approval, or global convergence claim
is established.

## Review Conclusion

M11-3 is accepted mesh/solver foundation evidence with explicitly reconciled
count history and bounded scope.
